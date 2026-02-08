from pathlib import Path

import pytest

from src.agent.orchestrator import AgentOrchestrator
from src.core.settings import Settings


@pytest.mark.asyncio
async def test_agent_orchestrator_returns_structured_default_output(tmp_path):
    settings = Settings(skills_dir=Path("skills"), config_dir=Path("config/pipelines"))
    orchestrator = AgentOrchestrator(settings=settings)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    result = await orchestrator.run_extraction(
        pipeline_id="credit-agreement",
        workspace_path=workspace,
        document_paths=[],
    )

    field_paths = {field.field_path for field in result.output.fields}
    assert "borrower" in field_paths
    assert "interest_rate" in field_paths
    assert result.output.agent_session_id is not None
