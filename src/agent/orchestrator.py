"""Central agent orchestrator for extraction runs."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

try:
    import fitz
except ImportError:  # pragma: no cover
    fitz = None

from ..core.config_loader import (
    ConfigLoader,
    ExtractionPipelineConfig,
    FieldSchemaConfig,
    FieldStrategyConfig,
)
from ..core.schemas import CitationOutput, ExtractedFieldOutput, ExtractionResultOutput
from ..core.settings import Settings, get_settings
from ..extraction.citation_builder import CitationBuilder
from ..extraction.field_extractor import FieldExtractor
from ..extraction.structure_extractor import DocumentStructureExtractor
from ..integrations.llm_base import LLMClientProtocol
from ..integrations.llm_factory import get_llm_client
from .budget import BudgetTracker, budget_for_pipeline
from .prompt_builder import PromptBuilder
from .result_parser import ResultParser
from .session_manager import SessionManager
from .skill_registry import SkillDefinition, SkillRegistry

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AgentOrchestratorResult:
    output: ExtractionResultOutput
    prompt: str


@dataclass(slots=True)
class DocumentContext:
    path: Path
    page_texts: list[str]
    page_index: list[dict[str, Any]]


class AgentOrchestrator:
    """
    Orchestrates extraction execution through a model-agnostic LLM runtime.

    Hybrid strategy routing:
    - `direct`: quick structured extraction from indexed snippets.
    - `skill`: field-specific skill instructions + structured extraction.
    - `cross_validate`: extract from multiple documents and reconcile.
    """

    def __init__(
        self,
        *,
        settings: Optional[Settings] = None,
        config_loader: Optional[ConfigLoader] = None,
        skill_registry: Optional[SkillRegistry] = None,
        session_manager: Optional[SessionManager] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        result_parser: Optional[ResultParser] = None,
        llm_client: Optional[LLMClientProtocol] = None,
    ):
        self.settings = settings or get_settings()
        self.config_loader = config_loader or ConfigLoader(str(self.settings.config_dir))
        self.skill_registry = skill_registry or SkillRegistry(self.settings.skills_dir)
        self.session_manager = session_manager or SessionManager()
        self.prompt_builder = prompt_builder or PromptBuilder(self.skill_registry)
        self.result_parser = result_parser or ResultParser()
        self.llm_client = llm_client or get_llm_client(self.settings)

        self._legacy_field_extractor = FieldExtractor(claude_client=self.llm_client)
        self._legacy_structure_extractor = DocumentStructureExtractor(
            claude_client=self.llm_client
        )
        self._legacy_citation_builder = CitationBuilder()

    async def run_extraction(
        self,
        *,
        pipeline_id: str,
        workspace_path: Path,
        document_paths: list[Path],
    ) -> AgentOrchestratorResult:
        """Execute extraction pipeline for a prepared run workspace."""
        config = self.config_loader.load_extraction_pipeline(pipeline_id)
        field_skill_names = self.config_loader.list_extraction_skill_names(pipeline_id)

        session = self.session_manager.open(workspace_path)
        budget = BudgetTracker(pipeline_id, budget_for_pipeline(self.settings, pipeline_id))

        prompt = self.prompt_builder.build_extraction_prompt(
            config=config,
            workspace_path=workspace_path,
            document_paths=document_paths,
            field_skill_names=field_skill_names,
        )

        output = await self._run_hybrid(
            session_id=session.session_id,
            prompt=prompt,
            config=config,
            document_paths=document_paths,
            budget=budget,
            field_skill_names=field_skill_names,
        )

        self.session_manager.save(
            session,
            extra={
                "pipeline_id": pipeline_id,
                "turns_used": budget.turns_used,
                "cost_used_usd": budget.cost_used_usd,
            },
        )
        return AgentOrchestratorResult(output=output, prompt=prompt)

    async def _run_hybrid(
        self,
        *,
        session_id: str,
        prompt: str,
        config: ExtractionPipelineConfig,
        document_paths: list[Path],
        budget: BudgetTracker,
        field_skill_names: dict[str, str],
    ) -> ExtractionResultOutput:
        logger.info(
            "Running hybrid extraction path for pipeline=%s provider=%s",
            config.id,
            self.settings.llm_provider,
        )

        if not document_paths:
            return self._default_output(config=config, session_id=session_id)

        document_contexts = self._prepare_document_contexts(document_paths)
        if not document_contexts:
            return self._default_output(config=config, session_id=session_id)

        fields: list[ExtractedFieldOutput] = []
        notes: list[str] = []

        for field_name, field_config in config.extraction_schema.items():
            strategy = self._resolve_strategy(field_config)
            candidates: list[ExtractedFieldOutput] = []

            for context in document_contexts:
                budget.record_turn()
                candidate = await self._extract_field_candidate(
                    field_name=field_name,
                    field_config=field_config,
                    strategy=strategy,
                    field_skill_name=field_skill_names.get(field_name),
                    context=context,
                )
                if candidate:
                    candidates.append(candidate)

            if not candidates:
                fields.append(
                    ExtractedFieldOutput(
                        field_path=field_name,
                        value=None,
                        confidence=0.0,
                        notes=f"no evidence found ({strategy.value})",
                    )
                )
                continue

            if strategy == FieldStrategyConfig.CROSS_VALIDATE:
                merged = self._merge_cross_validated(field_name, candidates)
                notes.append(f"{field_name}:cross_validated:{len(candidates)}")
            else:
                merged = max(candidates, key=lambda item: item.confidence)
                notes.append(f"{field_name}:{strategy.value}:{len(candidates)}")

            fields.append(merged)

        return ExtractionResultOutput(
            fields=fields,
            extraction_notes=notes,
            agent_session_id=session_id,
        )

    def _prepare_document_contexts(self, document_paths: list[Path]) -> list[DocumentContext]:
        contexts: list[DocumentContext] = []

        for path in document_paths:
            if fitz is None:
                logger.warning("PyMuPDF unavailable, skipping indexed context for %s", path)
                continue

            try:
                with fitz.open(str(path)) as doc:
                    page_texts = [doc[i].get_text() for i in range(len(doc))]
                page_index = self._build_page_index(page_texts)
                contexts.append(
                    DocumentContext(
                        path=path,
                        page_texts=page_texts,
                        page_index=page_index,
                    )
                )
            except Exception:
                logger.exception("Failed to prepare document context for %s", path)

        return contexts

    def _build_page_index(self, page_texts: list[str]) -> list[dict[str, Any]]:
        heading_patterns = [
            re.compile(r"^ARTICLE\s+[IVX]+", re.IGNORECASE),
            re.compile(r"^Section\s+\d+\.\d+", re.IGNORECASE),
            re.compile(r"^SECTION\s+\d+\.\d+", re.IGNORECASE),
            re.compile(r"^SCHEDULE\s+", re.IGNORECASE),
            re.compile(r"^EXHIBIT\s+[A-Z]", re.IGNORECASE),
            re.compile(r"^APPENDIX\s+[A-Z]", re.IGNORECASE),
        ]

        entries: list[dict[str, Any]] = []
        for page_num, text in enumerate(page_texts, start=1):
            for raw_line in text.splitlines()[:40]:
                line = raw_line.strip()
                if len(line) < 4:
                    continue
                if any(pattern.match(line) for pattern in heading_patterns):
                    entries.append({"title": line[:180], "page": page_num})
                    break
        return entries

    def _resolve_strategy(self, field_config: FieldSchemaConfig) -> FieldStrategyConfig:
        if field_config.field_strategy:
            return field_config.field_strategy
        if field_config.cross_validate:
            return FieldStrategyConfig.CROSS_VALIDATE
        if field_config.skill:
            return FieldStrategyConfig.SKILL
        return FieldStrategyConfig.DIRECT

    async def _extract_field_candidate(
        self,
        *,
        field_name: str,
        field_config: FieldSchemaConfig,
        strategy: FieldStrategyConfig,
        field_skill_name: Optional[str],
        context: DocumentContext,
    ) -> Optional[ExtractedFieldOutput]:
        snippets = self._collect_relevant_snippets(
            likely_sections=field_config.likely_sections,
            page_index=context.page_index,
            page_texts=context.page_texts,
            max_pages=6,
        )

        if not snippets:
            snippets = [
                {
                    "page": idx + 1,
                    "text": text[:2500],
                }
                for idx, text in enumerate(context.page_texts[:4])
            ]

        if strategy == FieldStrategyConfig.SKILL:
            skill = self._resolve_skill(field_skill_name)
            payload = await self._extract_with_skill(
                field_name=field_name,
                field_config=field_config,
                skill=skill,
                snippets=snippets,
                document_name=context.path.name,
            )
        else:
            payload = await self._extract_direct(
                field_name=field_name,
                field_config=field_config,
                snippets=snippets,
                document_name=context.path.name,
                strict=(strategy == FieldStrategyConfig.CROSS_VALIDATE),
            )

        if not payload:
            return None

        citation_payload = payload.get("citation") or {}
        citation = CitationOutput(
            document_id=context.path.name,
            page_number=int(citation_payload.get("page_number") or 0),
            extracted_text=str(citation_payload.get("extracted_text") or ""),
            confidence=float(payload.get("confidence") or 0.0),
        )

        return ExtractedFieldOutput(
            field_path=field_name,
            value=payload.get("value"),
            confidence=float(payload.get("confidence") or 0.0),
            citation=citation,
            notes=payload.get("notes"),
        )

    def _collect_relevant_snippets(
        self,
        *,
        likely_sections: list[str],
        page_index: list[dict[str, Any]],
        page_texts: list[str],
        max_pages: int,
    ) -> list[dict[str, Any]]:
        if not likely_sections:
            return []

        section_pages: set[int] = set()
        for section in likely_sections:
            needle = section.lower()
            for entry in page_index:
                if needle in str(entry.get("title", "")).lower():
                    page = int(entry.get("page", 0))
                    if page > 0:
                        section_pages.add(page)

        snippets: list[dict[str, Any]] = []
        for page in sorted(section_pages)[:max_pages]:
            if 1 <= page <= len(page_texts):
                snippets.append(
                    {
                        "page": page,
                        "text": page_texts[page - 1][:3000],
                    }
                )
        return snippets

    def _resolve_skill(self, skill_name: Optional[str]) -> Optional[SkillDefinition]:
        if not skill_name:
            return None
        return self.skill_registry.resolve_field_skill(skill_name)

    async def _extract_direct(
        self,
        *,
        field_name: str,
        field_config: FieldSchemaConfig,
        snippets: list[dict[str, Any]],
        document_name: str,
        strict: bool,
    ) -> dict:
        schema_hint = {
            "type": field_config.type,
            "description": field_config.description,
            "properties": field_config.properties,
            "items": field_config.items,
        }

        prompt = (
            "Extract one field from legal-document snippets.\n"
            f"field_path: {field_name}\n"
            f"schema_hint: {json.dumps(schema_hint, ensure_ascii=True)}\n"
            f"strict_mode: {strict}\n"
            f"document: {document_name}\n"
            f"snippets: {json.dumps(snippets, ensure_ascii=True)}\n"
            "Return JSON exactly: "
            '{"value": <any|null>, "confidence": <0-1>, '
            '"citation": {"page_number": <int>, "extracted_text": "<string>"}, '
            '"notes": "<optional>"}'
        )
        return await self.llm_client.query_json(prompt=prompt, max_tokens=1200)

    async def _extract_with_skill(
        self,
        *,
        field_name: str,
        field_config: FieldSchemaConfig,
        skill: Optional[SkillDefinition],
        snippets: list[dict[str, Any]],
        document_name: str,
    ) -> dict:
        skill_instructions = skill.body if skill else "No skill content found."
        schema_hint = {
            "type": field_config.type,
            "description": field_config.description,
            "properties": field_config.properties,
            "items": field_config.items,
        }

        prompt = (
            "You are a field extraction specialist.\n"
            f"field_path: {field_name}\n"
            f"document: {document_name}\n"
            f"schema_hint: {json.dumps(schema_hint, ensure_ascii=True)}\n"
            f"skill_instructions: {skill_instructions}\n"
            f"snippets: {json.dumps(snippets, ensure_ascii=True)}\n"
            "Return JSON exactly: "
            '{"value": <any|null>, "confidence": <0-1>, '
            '"citation": {"page_number": <int>, "extracted_text": "<string>"}, '
            '"notes": "<optional>"}'
        )
        return await self.llm_client.query_json(prompt=prompt, max_tokens=1800)

    def _merge_cross_validated(
        self,
        field_name: str,
        candidates: list[ExtractedFieldOutput],
    ) -> ExtractedFieldOutput:
        best = max(candidates, key=lambda item: item.confidence)

        canonical = self._canonical_value(best.value)
        mismatches = 0
        for candidate in candidates:
            if self._canonical_value(candidate.value) != canonical:
                mismatches += 1

        if mismatches:
            penalty = min(0.35, 0.1 * mismatches)
            best.confidence = max(0.0, best.confidence - penalty)
            best.notes = f"cross-document mismatches={mismatches}"
        else:
            best.notes = "cross-document match"

        return best

    def _canonical_value(self, value: Any) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value, sort_keys=True, ensure_ascii=True)
        return str(value)

    def _default_output(
        self,
        *,
        config: ExtractionPipelineConfig,
        session_id: str,
    ) -> ExtractionResultOutput:
        return ExtractionResultOutput(
            fields=[
                ExtractedFieldOutput(
                    field_path=field_path,
                    value=None,
                    confidence=0.0,
                    citation=None,
                    notes="No extraction value available",
                )
                for field_path in config.extraction_schema.keys()
            ],
            extraction_notes=[
                "agent_runtime_default_output",
                "no fields extracted from provided documents",
            ],
            agent_session_id=session_id,
        )

    def write_debug_prompt(self, workspace_path: Path, prompt: str) -> Path:
        target = workspace_path / "agent_prompt.txt"
        target.write_text(prompt, encoding="utf-8")
        return target

    def write_debug_output(self, workspace_path: Path, output: ExtractionResultOutput) -> Path:
        target = workspace_path / "agent_output.json"
        target.write_text(
            json.dumps(output.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return target
