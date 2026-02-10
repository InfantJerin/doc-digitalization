from __future__ import annotations

from pathlib import Path

import pytest

from src.core.config_loader import ConfigLoader
from src.core.models import (
    DealPageIndex,
    DocumentPageIndex,
)
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


class FakeDocumentIndexer:
    async def build_index(
        self,
        pdf_path,
        document_id: str,
        document_type: str = "",
        *,
        use_llm_keywords: bool = False,
        skip_layout_analysis: bool = False,
    ):
        return DocumentPageIndex(
            document_id=document_id,
            document_type=document_type or "credit_agreement",
            total_pages=1,
        )


class FakeDealIndexer:
    async def build_deal_index(self, deal_id: str, document_indexes, *, detect_cross_references: bool = True):
        return DealPageIndex(
            deal_id=deal_id,
            document_registry={doc_id: idx.document_type for doc_id, idx in document_indexes.items()},
            document_indexes=document_indexes,
        )


class FakeOrchestrator:
    def __init__(self):
        self.last_kwargs = {}

    async def run_extraction(self, **kwargs):
        self.last_kwargs = kwargs

        class _Result:
            def __init__(self):
                self.output = ExtractionResultOutput(
                    fields=[
                        ExtractedFieldOutput(
                            field_path="borrower",
                            value={"legal_name": "Acme"},
                            confidence=0.99,
                        )
                    ],
                    extraction_notes=["ok"],
                    agent_session_id="session-idx",
                )
                self.prompt = "prompt"

        return _Result()

    def write_debug_prompt(self, workspace_path: Path, prompt: str):
        path = workspace_path / "agent_prompt.txt"
        path.write_text(prompt, encoding="utf-8")
        return path

    def write_debug_output(self, workspace_path: Path, output: ExtractionResultOutput):
        path = workspace_path / "agent_output.json"
        path.write_text(output.model_dump_json(), encoding="utf-8")
        return path


@pytest.mark.asyncio
async def test_extraction_service_passes_deal_index_to_orchestrator():
    orchestrator = FakeOrchestrator()
    service = ExtractionService(
        dms_client=FakeDMSClient(),
        config_loader=ConfigLoader("config/pipelines"),
        extraction_repo=ExtractionRepository(),
        review_repo=ReviewRepository(),
        orchestrator=orchestrator,
        workspace_manager=ExtractionWorkspaceManager(),
        document_indexer=FakeDocumentIndexer(),
        deal_indexer=FakeDealIndexer(),
    )

    run = await service.run_extraction(
        deal_id="deal-1",
        pipeline_id="credit-agreement",
        document_ids=["doc-1"],
        triggered_by="test",
    )

    assert orchestrator.last_kwargs.get("deal_index") is not None
    workspace_path = Path(run.metadata["workspace_path"])
    assert (workspace_path / "index" / "doc_index_doc-1.json").exists()
    assert (workspace_path / "index" / "deal_index.json").exists()
