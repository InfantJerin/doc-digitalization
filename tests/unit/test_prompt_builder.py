from pathlib import Path

from src.agent.prompt_builder import PromptBuilder
from src.agent.skill_registry import SkillRegistry
from src.core.config_loader import ExtractionPipelineConfig


def test_prompt_builder_includes_config_and_workspace(tmp_path):
    registry = SkillRegistry(Path("skills"))
    builder = PromptBuilder(registry)

    config = ExtractionPipelineConfig(
        id="demo",
        name="Demo",
        document_types=[{"type": "credit_agreement", "required": True}],
        extraction_schema={
            "borrower": {
                "type": "object",
                "description": "Borrower",
                "likely_sections": ["Preamble"],
            }
        },
    )

    prompt = builder.build_extraction_prompt(
        config=config,
        workspace_path=tmp_path,
        document_paths=[tmp_path / "doc.pdf"],
        field_skill_names={"borrower": "borrower"},
    )

    assert "Pipeline Configuration" in prompt
    assert "borrower" in prompt
    assert str(tmp_path) in prompt
