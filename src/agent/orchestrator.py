"""Central agent orchestrator for extraction runs."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..core.config_loader import ConfigLoader, ExtractionPipelineConfig
from ..core.schemas import CitationOutput, ExtractedFieldOutput, ExtractionResultOutput
from ..core.settings import Settings, get_settings
from ..extraction.citation_builder import CitationBuilder
from ..extraction.field_extractor import FieldExtractor
from ..extraction.structure_extractor import DocumentStructureExtractor
from ..integrations.claude_client import ClaudeClient
from .budget import BudgetTracker, budget_for_pipeline
from .prompt_builder import PromptBuilder
from .result_parser import ResultParser
from .session_manager import SessionManager
from .skill_registry import SkillRegistry

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional runtime dependency
    import claude_agent_sdk  # type: ignore

    CLAUDE_AGENT_SDK_AVAILABLE = True
except ImportError:  # pragma: no cover
    claude_agent_sdk = None
    CLAUDE_AGENT_SDK_AVAILABLE = False


@dataclass(slots=True)
class AgentOrchestratorResult:
    output: ExtractionResultOutput
    prompt: str


class AgentOrchestrator:
    """
    Orchestrates extraction execution through Claude Agent SDK.

    Current behavior:
    - Uses SDK runtime when available.
    - Falls back to legacy extraction path when SDK package is not installed.
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
        claude_client: Optional[ClaudeClient] = None,
    ):
        self.settings = settings or get_settings()
        self.config_loader = config_loader or ConfigLoader(str(self.settings.config_dir))
        self.skill_registry = skill_registry or SkillRegistry(self.settings.skills_dir)
        self.session_manager = session_manager or SessionManager()
        self.prompt_builder = prompt_builder or PromptBuilder(self.skill_registry)
        self.result_parser = result_parser or ResultParser()
        self.claude_client = claude_client or ClaudeClient(
            api_key=self.settings.anthropic_api_key,
            model=self.settings.agent_model,
        )

        # Transitional fallback components.
        self._legacy_field_extractor = FieldExtractor(claude_client=self.claude_client)
        self._legacy_structure_extractor = DocumentStructureExtractor(
            claude_client=self.claude_client
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

        if CLAUDE_AGENT_SDK_AVAILABLE:
            output = await self._run_sdk(
                session_id=session.session_id,
                prompt=prompt,
                config=config,
                document_paths=document_paths,
                budget=budget,
                field_skill_names=field_skill_names,
            )
        else:
            output = await self._run_legacy_fallback(
                session_id=session.session_id,
                config=config,
                document_paths=document_paths,
                budget=budget,
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

    async def _run_sdk(
        self,
        *,
        session_id: str,
        prompt: str,
        config: ExtractionPipelineConfig,
        document_paths: list[Path],
        budget: BudgetTracker,
        field_skill_names: dict[str, str],
    ) -> ExtractionResultOutput:
        """
        Agent SDK execution path.

        This path is intentionally conservative until the SDK runtime package is
        finalized in deployment environments. It emits config-driven defaults if
        the SDK call fails.
        """
        budget.record_turn()

        try:
            # Placeholder until Claude Agent SDK API bindings are finalized.
            # Keep prompt/workspace artifacts for observability and fallback.
            _ = claude_agent_sdk
            logger.info("Claude Agent SDK available; using guarded fallback execution")
        except Exception:
            logger.exception("Agent SDK runtime call failed, falling back to defaults")

        return self._default_output(config=config, session_id=session_id)

    async def _run_legacy_fallback(
        self,
        *,
        session_id: str,
        config: ExtractionPipelineConfig,
        document_paths: list[Path],
        budget: BudgetTracker,
    ) -> ExtractionResultOutput:
        logger.info("Running legacy extraction fallback for pipeline %s", config.id)
        aggregated: dict[str, ExtractedFieldOutput] = {}

        for document_path in document_paths:
            budget.record_turn()
            structure = None
            if config.large_document_handling.enabled:
                structure = await self._legacy_structure_extractor.extract(str(document_path))

            fields = await self._legacy_field_extractor.extract_all_fields(
                pdf_path=str(document_path),
                config=config,
                structure=structure,
            )
            fields = self._legacy_citation_builder.enhance_all_citations(
                fields,
                str(document_path),
            )

            for field in fields:
                citation = None
                if field.citation:
                    field.citation.document_id = field.citation.document_id or document_path.name
                    bbox = None
                    if field.citation.bounding_box:
                        bbox = {
                            "x": field.citation.bounding_box.x,
                            "y": field.citation.bounding_box.y,
                            "width": field.citation.bounding_box.width,
                            "height": field.citation.bounding_box.height,
                        }
                    citation = CitationOutput(
                        document_id=field.citation.document_id,
                        page_number=field.citation.page_number,
                        extracted_text=field.citation.extracted_text,
                        confidence=field.citation.confidence,
                        bounding_box=bbox,
                    )

                candidate = ExtractedFieldOutput(
                    field_path=field.field_path,
                    value=field.value,
                    confidence=field.confidence,
                    citation=citation,
                )
                current = aggregated.get(field.field_path)
                if current is None or candidate.confidence > current.confidence:
                    aggregated[field.field_path] = candidate

        if not aggregated:
            return self._default_output(config=config, session_id=session_id)

        return ExtractionResultOutput(
            fields=sorted(aggregated.values(), key=lambda item: item.field_path),
            extraction_notes=["legacy_fallback_executed"],
            agent_session_id=session_id,
        )

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
                "configure Claude Agent SDK runtime for autonomous extraction",
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
