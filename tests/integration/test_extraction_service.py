from __future__ import annotations

from pathlib import Path

import pytest

from src.core.config_loader import ConfigLoader
from src.core.schemas import ExtractedFieldOutput, ExtractionResultOutput
from src.database.repositories.extraction_repo import ExtractionRepository
from src.database.repositories.review_repo import ReviewRepository
from src.extraction.service import ExtractionService
from src.extraction.workspace import ExtractionWorkspaceManager


class FakeDMSClient:
    async def download_document(self, document_id: str, target_path: str | None = None) -> str:
        path = Path(target_path or f"/tmp/{document_id}.pdf")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"%PDF-1.4\n%fake")
        return str(path)


class FakeOrchestrator:
    def __init__(self, output: ExtractionResultOutput):
        self.output = output

    async def run_extraction(self, **kwargs):
        class _Result:
            def __init__(self, out):
                self.output = out
                self.prompt = "test prompt"

        return _Result(self.output)

    def write_debug_prompt(self, workspace_path: Path, prompt: str):
        path = workspace_path / "agent_prompt.txt"
        path.write_text(prompt, encoding="utf-8")
        return path

    def write_debug_output(self, workspace_path: Path, output: ExtractionResultOutput):
        path = workspace_path / "agent_output.json"
        path.write_text(output.model_dump_json(), encoding="utf-8")
        return path


@pytest.mark.asyncio
async def test_extraction_service_persists_run_and_creates_review(tmp_path):
    output = ExtractionResultOutput(
        fields=[ExtractedFieldOutput(field_path="borrower", value={"legal_name": "Acme"}, confidence=0.4)],
        extraction_notes=["test"],
        agent_session_id="session-1",
    )

    service = ExtractionService(
        dms_client=FakeDMSClient(),
        config_loader=ConfigLoader("config/pipelines"),
        extraction_repo=ExtractionRepository(),
        review_repo=ReviewRepository(),
        orchestrator=FakeOrchestrator(output),
        workspace_manager=ExtractionWorkspaceManager(),
    )

    run = await service.run_extraction(
        deal_id="deal-1",
        pipeline_id="credit-agreement",
        document_ids=["doc-1"],
        triggered_by="test",
    )

    assert run.status.value == "awaiting_review"
    assert run.agent_session_id == "session-1"
    assert run.metadata.get("review_task_id")
