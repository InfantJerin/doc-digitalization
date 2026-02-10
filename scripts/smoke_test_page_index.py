#!/usr/bin/env python3
"""Build and validate the PageIndex pipeline against a local PDF."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from src.indexing.deal_indexer import DealIndexer
from src.indexing.document_indexer import DocumentIndexer
from src.indexing.index_store import IndexStore
from src.tools.index_tools import IndexTools


async def run_smoke_test(document_path: Path, output_path: Path | None) -> int:
    workspace_root = Path("/tmp/page_index_smoke")
    workspace_root.mkdir(parents=True, exist_ok=True)

    document_id = "sample_doc_1"
    deal_id = "smoke_deal_1"

    doc_indexer = DocumentIndexer()
    deal_indexer = DealIndexer()
    store = IndexStore(workspace_root)

    doc_index = await doc_indexer.build_index(
        pdf_path=document_path,
        document_id=document_id,
        document_type="credit_agreement",
    )
    store.save_document_index(doc_index)

    deal_index = await deal_indexer.build_deal_index(
        deal_id=deal_id,
        document_indexes={document_id: doc_index},
        detect_cross_references=True,
    )
    store.save_deal_index(deal_index)

    tools = IndexTools(deal_index)
    summary = tools.get_index_summary()

    sample_queries = {
        "find_section('Definitions')": tools.find_section("Definitions"),
        "lookup_keyword('EBITDA')": tools.lookup_keyword("EBITDA"),
        "find_term_across_docs('Leverage Ratio')": tools.find_term_across_docs("Leverage Ratio"),
        "resolve_reference(document_id, 1)": tools.resolve_reference(document_id, 1),
    }

    result = {
        "workspace_root": str(workspace_root),
        "document_path": str(document_path),
        "document_index_file": str(workspace_root / "index" / f"doc_index_{document_id}.json"),
        "deal_index_file": str(workspace_root / "index" / "deal_index.json"),
        "summary": summary,
        "tool_samples": sample_queries,
    }

    print(json.dumps(result, indent=2, ensure_ascii=True))
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2, ensure_ascii=True), encoding="utf-8")
        print(f"\nSmoke test output written to: {output_path}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run PageIndex smoke test with local sample PDF")
    parser.add_argument(
        "--document-path",
        default="resources/credit agreement/AbbieVie Term Loan Credit Agreement.pdf",
        help="Path to source PDF",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional JSON output file path",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    document_path = Path(args.document_path)
    if not document_path.exists():
        print(f"Document path not found: {document_path}")
        return 2

    output_path = Path(args.output) if args.output else None
    return asyncio.run(run_smoke_test(document_path, output_path))


if __name__ == "__main__":
    raise SystemExit(main())
