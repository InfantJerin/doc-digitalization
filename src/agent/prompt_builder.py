"""System prompt construction for extraction agent runs."""

from __future__ import annotations

import json
from pathlib import Path

from ..core.config_loader import ExtractionPipelineConfig
from .skill_registry import SkillRegistry


class PromptBuilder:
    """Builds deterministic prompts from config + skill metadata."""

    def __init__(self, registry: SkillRegistry):
        self.registry = registry

    def build_extraction_prompt(
        self,
        *,
        config: ExtractionPipelineConfig,
        workspace_path: Path,
        document_paths: list[Path],
        field_skill_names: dict[str, str],
    ) -> str:
        self.registry.ensure_discovered()

        orchestrator_skill = self.registry.get("extraction-orchestrator")
        orchestrator_body = (
            orchestrator_skill.body
            if orchestrator_skill
            else "No orchestrator skill found; follow config-driven extraction strictly."
        )

        compact_index = self.registry.get_compact_index()
        schema_payload = {
            key: {
                "type": value.type,
                "description": value.description,
                "likely_sections": value.likely_sections,
                "sources": value.sources,
                "cross_validate": value.cross_validate,
                "skill": field_skill_names.get(key),
            }
            for key, value in config.extraction_schema.items()
        }

        return (
            "You are a document extraction coding agent.\n\n"
            "## Orchestrator Skill\n"
            f"{orchestrator_body}\n\n"
            "## Available Skills (compact index)\n"
            f"{json.dumps(compact_index, indent=2)}\n\n"
            "## Pipeline Configuration\n"
            f"{json.dumps(schema_payload, indent=2)}\n\n"
            "## Workspace\n"
            f"workspace: {workspace_path}\n"
            f"documents: {json.dumps([str(path) for path in document_paths], indent=2)}\n\n"
            "## Output Contract\n"
            "Return ExtractionResultOutput JSON exactly with fields[], extraction_notes[], and optional agent_session_id."
        )
