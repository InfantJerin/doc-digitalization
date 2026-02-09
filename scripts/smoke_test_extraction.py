#!/usr/bin/env python3
"""Run a local extraction smoke test against a sample PDF in this repository."""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
from pathlib import Path

from src.extraction.service import ExtractionService
from src.core.config_loader import ConfigLoader
from src.database.repositories.extraction_repo import ExtractionRepository
from src.database.repositories.review_repo import ReviewRepository


class LocalFileDMSClient:
    """Minimal DMS adapter that serves local files by document id."""

    def __init__(self, doc_map: dict[str, Path]):
        self.doc_map = doc_map

    async def download_document(self, document_id: str, target_path: str | None = None) -> str:
        source = self.doc_map.get(document_id)
        if source is None:
            raise FileNotFoundError(f"No local file mapped for document id: {document_id}")
        if not source.exists():
            raise FileNotFoundError(f"Mapped file does not exist: {source}")

        if target_path is None:
            return str(source)

        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return str(target)


async def run_smoke_test(
    *,
    pipeline_id: str,
    deal_id: str,
    document_id: str,
    document_path: Path,
    triggered_by: str,
    output_path: Path | None,
) -> int:
    service = ExtractionService(
        dms_client=LocalFileDMSClient({document_id: document_path}),
        config_loader=ConfigLoader("config/pipelines"),
        extraction_repo=ExtractionRepository(),
        review_repo=ReviewRepository(),
    )

    run = await service.run_extraction(
        deal_id=deal_id,
        pipeline_id=pipeline_id,
        document_ids=[document_id],
        triggered_by=triggered_by,
    )

    result = {
        "run_id": run.id,
        "status": run.status.value,
        "pipeline_id": run.pipeline_id,
        "deal_id": run.deal_id,
        "agent_session_id": run.agent_session_id,
        "field_count": len(run.extracted_fields),
        "fields": [
            {
                "field_path": field.field_path,
                "value": field.override_value if field.overridden else field.value,
                "confidence": field.confidence,
                "citation": {
                    "document_id": field.citation.document_id,
                    "page_number": field.citation.page_number,
                    "extracted_text": field.citation.extracted_text,
                }
                if field.citation
                else None,
                "notes": field.override_justification if field.overridden else None,
            }
            for field in run.extracted_fields
        ],
        "metadata": run.metadata,
        "error_message": run.error_message,
    }

    print(json.dumps(result, indent=2, ensure_ascii=True, default=str))

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2, ensure_ascii=True), encoding="utf-8")
        print(f"\nSmoke test output written to: {output_path}")

    return 0 if run.status.value != "failed" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run extraction smoke test with local sample PDF")
    parser.add_argument(
        "--pipeline-id",
        default="credit-agreement",
        help="Extraction pipeline id (default: credit-agreement)",
    )
    parser.add_argument(
        "--deal-id",
        default="smoke-deal-001",
        help="Deal id for the smoke test run",
    )
    parser.add_argument(
        "--document-id",
        default="sample-credit-agreement",
        help="Logical document id used in the run",
    )
    parser.add_argument(
        "--document-path",
        default="resources/credit agreement/AbbieVie Term Loan Credit Agreement.pdf",
        help="Path to sample PDF",
    )
    parser.add_argument(
        "--triggered-by",
        default="smoke-test",
        help="Actor tag for the run",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional path to write JSON output",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    doc_path = Path(args.document_path)
    if not doc_path.exists():
        print(f"Document path not found: {doc_path}")
        return 2

    output_path = Path(args.output) if args.output else None

    return asyncio.run(
        run_smoke_test(
            pipeline_id=args.pipeline_id,
            deal_id=args.deal_id,
            document_id=args.document_id,
            document_path=doc_path,
            triggered_by=args.triggered_by,
            output_path=output_path,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
