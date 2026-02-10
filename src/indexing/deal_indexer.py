"""Deal-level index assembler — merges per-document indexes into a deal index."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Optional

from ..core.models import (
    DealPageIndex,
    DocumentPageIndex,
    KeywordEntry,
)
from ..integrations.llm_base import LLMClientProtocol
from .cross_reference_detector import CrossReferenceDetector

logger = logging.getLogger(__name__)


class DealIndexer:
    """Assembles a deal-level index from per-document indexes.

    1. Builds document registry (doc_id -> doc_type)
    2. Merges per-document keyword indexes into unified index
    3. Runs ``CrossReferenceDetector`` across document pairs
    """

    def __init__(
        self,
        *,
        llm_client: Optional[LLMClientProtocol] = None,
        cross_reference_detector: Optional[CrossReferenceDetector] = None,
    ):
        self.llm_client = llm_client
        self.cross_reference_detector = cross_reference_detector or CrossReferenceDetector(
            llm_client=llm_client,
        )

    async def build_deal_index(
        self,
        deal_id: str,
        document_indexes: dict[str, DocumentPageIndex],
        *,
        detect_cross_references: bool = True,
    ) -> DealPageIndex:
        """Build a deal-level index from per-document indexes.

        Args:
            deal_id: Unique deal identifier.
            document_indexes: Map of doc_id -> DocumentPageIndex.
            detect_cross_references: Whether to run cross-reference detection.

        Returns:
            A ``DealPageIndex`` spanning all documents.
        """
        logger.info(
            "Building deal index for %s with %d documents",
            deal_id,
            len(document_indexes),
        )

        # 1. Build document registry
        document_registry = {
            doc_id: idx.document_type
            for doc_id, idx in document_indexes.items()
        }

        # 2. Merge keyword indexes
        unified_keywords = self._merge_keywords(document_indexes)

        # 3. Detect cross-references
        cross_references = []
        if detect_cross_references and len(document_indexes) > 1:
            for source_doc_id, source_index in document_indexes.items():
                try:
                    refs = await self.cross_reference_detector.detect_cross_references(
                        source_doc_id=source_doc_id,
                        source_index=source_index,
                        all_indexes=document_indexes,
                    )
                    cross_references.extend(refs)
                except Exception:
                    logger.warning(
                        "Cross-reference detection failed for %s",
                        source_doc_id,
                    )

        return DealPageIndex(
            deal_id=deal_id,
            document_registry=document_registry,
            document_indexes=document_indexes,
            unified_keywords=unified_keywords,
            cross_references=cross_references,
        )

    def _merge_keywords(
        self, document_indexes: dict[str, DocumentPageIndex]
    ) -> list[KeywordEntry]:
        """Merge per-document keyword indexes into a unified index.

        Preserves document provenance by including doc_id in section names.
        """
        merged: dict[str, KeywordEntry] = {}

        for doc_id, doc_index in document_indexes.items():
            for kw in doc_index.keyword_index:
                canonical = kw.canonical_term
                if canonical in merged:
                    existing = merged[canonical]
                    # Merge pages with doc provenance
                    for page in kw.pages:
                        if page not in existing.pages:
                            existing.pages.append(page)
                    for sec in kw.sections:
                        tagged = f"{doc_id}:{sec}"
                        if tagged not in existing.sections:
                            existing.sections.append(tagged)
                    # Keep the first definition page found
                    if kw.definition_page and not existing.definition_page:
                        existing.definition_page = kw.definition_page
                else:
                    merged[canonical] = KeywordEntry(
                        term=kw.term,
                        canonical_term=canonical,
                        pages=list(kw.pages),
                        sections=[f"{doc_id}:{sec}" for sec in kw.sections],
                        term_type=kw.term_type,
                        definition_page=kw.definition_page,
                    )

        return sorted(
            merged.values(),
            key=lambda e: len(e.pages),
            reverse=True,
        )
