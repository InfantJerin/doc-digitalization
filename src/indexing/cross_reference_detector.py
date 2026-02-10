"""Pass 2b: Cross-document reference detection.

Finds references spanning documents in a deal (e.g. compliance cert ->
credit agreement -> financial statements) using regex candidates + LLM
resolution.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from ..core.models import (
    CrossDocumentReference,
    DocumentPageIndex,
    PageLayout,
)
from ..integrations.llm_base import LLMClientProtocol

logger = logging.getLogger(__name__)

# Patterns that indicate cross-document references
_CROSS_REF_PATTERNS = [
    re.compile(
        r"as\s+defined\s+in\s+(?:Section|Article)\s+[\dIVX]+(?:\.\d+)?\s+of\s+the\s+([A-Z][A-Za-z\s]+(?:Agreement|Certificate|Statement))",
        re.IGNORECASE,
    ),
    re.compile(
        r"pursuant\s+to\s+(?:Section|Article)\s+[\dIVX]+(?:\.\d+)?\s+of\s+the\s+([A-Z][A-Za-z\s]+(?:Agreement|Certificate|Statement))",
        re.IGNORECASE,
    ),
    re.compile(
        r"in\s+accordance\s+with\s+(?:the\s+)?([A-Z][A-Za-z\s]+(?:Agreement|Certificate|Statement))",
        re.IGNORECASE,
    ),
    re.compile(
        r"under\s+the\s+([A-Z][A-Za-z\s]+(?:Agreement|Certificate|Statement))",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:the|this)\s+([A-Z][A-Za-z\s]+(?:Agreement|Certificate|Statement))\s+(?:dated|entered)",
        re.IGNORECASE,
    ),
]


class CrossReferenceDetector:
    """Detects cross-document references between documents in a deal.

    Two-phase approach:
    1. Regex candidate extraction from page text
    2. LLM resolution to map candidates to target documents
    """

    def __init__(self, *, llm_client: Optional[LLMClientProtocol] = None):
        self.llm_client = llm_client

    async def detect_cross_references(
        self,
        source_doc_id: str,
        source_index: DocumentPageIndex,
        all_indexes: dict[str, DocumentPageIndex],
    ) -> list[CrossDocumentReference]:
        """Detect references from source_doc to other documents.

        Args:
            source_doc_id: ID of the source document.
            source_index: The source document's page index.
            all_indexes: Map of doc_id -> DocumentPageIndex for all deal docs.

        Returns:
            List of resolved cross-document references.
        """
        # Phase 1: regex candidates
        candidates = self._extract_regex_candidates(
            source_doc_id, source_index.page_layouts
        )

        if not candidates:
            return []

        # Phase 2: LLM resolution (or heuristic fallback)
        if self.llm_client:
            return await self._llm_resolve(
                candidates, source_doc_id, all_indexes
            )
        else:
            return self._heuristic_resolve(candidates, source_doc_id, all_indexes)

    def _extract_regex_candidates(
        self,
        source_doc_id: str,
        page_layouts: list[PageLayout],
    ) -> list[dict]:
        """Extract raw reference candidates via regex."""
        candidates: list[dict] = []
        seen: set[str] = set()

        for layout in page_layouts:
            page_text = " ".join(layout.headers + layout.paragraphs)

            for pattern in _CROSS_REF_PATTERNS:
                for match in pattern.finditer(page_text):
                    ref_text = match.group(0).strip()
                    target_name = match.group(1).strip()

                    dedup_key = f"{layout.page_number}:{target_name.lower()}"
                    if dedup_key in seen:
                        continue
                    seen.add(dedup_key)

                    candidates.append({
                        "source_page": layout.page_number,
                        "reference_text": ref_text,
                        "target_name": target_name,
                    })

        return candidates

    async def _llm_resolve(
        self,
        candidates: list[dict],
        source_doc_id: str,
        all_indexes: dict[str, DocumentPageIndex],
    ) -> list[CrossDocumentReference]:
        """Use LLM to resolve reference candidates to target documents."""
        # Build document summary for LLM context
        doc_summaries: list[dict] = []
        for doc_id, idx in all_indexes.items():
            if doc_id == source_doc_id:
                continue
            top_sections = []
            if idx.structure:
                for node in idx.structure.get_all_nodes()[:10]:
                    top_sections.append(node.title)
            doc_summaries.append({
                "doc_id": doc_id,
                "doc_type": idx.document_type,
                "total_pages": idx.total_pages,
                "sections": top_sections,
            })

        if not doc_summaries:
            return []

        prompt = (
            "You are mapping cross-document references in a loan deal.\n\n"
            f"Source document: {source_doc_id}\n\n"
            f"Available target documents:\n{json.dumps(doc_summaries, indent=2)}\n\n"
            f"Reference candidates:\n{json.dumps(candidates[:30], indent=2)}\n\n"
            "For each candidate, determine which target document it refers to. "
            "If a candidate refers to the source document itself, skip it.\n"
            "Return JSON: {\"resolved\": [{\"candidate_index\": <int>, "
            "\"target_doc_id\": \"<string>\", \"target_node_id\": \"<string or empty>\", "
            "\"target_page\": <int or null>, \"confidence\": <0-1>}]}"
        )

        try:
            result = await self.llm_client.query_json(prompt=prompt, max_tokens=2000)
            resolved = result.get("resolved", [])
        except Exception:
            logger.warning("LLM cross-reference resolution failed, using heuristic")
            return self._heuristic_resolve(candidates, source_doc_id, all_indexes)

        references: list[CrossDocumentReference] = []
        for item in resolved:
            idx = item.get("candidate_index", -1)
            if idx < 0 or idx >= len(candidates):
                continue
            candidate = candidates[idx]
            target_doc_id = item.get("target_doc_id", "")
            if target_doc_id not in all_indexes or target_doc_id == source_doc_id:
                continue

            references.append(CrossDocumentReference(
                source_document_id=source_doc_id,
                source_page=candidate["source_page"],
                reference_text=candidate["reference_text"],
                target_document_id=target_doc_id,
                target_node_id=item.get("target_node_id", ""),
                target_page=item.get("target_page"),
                confidence=float(item.get("confidence", 0.5)),
            ))

        return references

    def _heuristic_resolve(
        self,
        candidates: list[dict],
        source_doc_id: str,
        all_indexes: dict[str, DocumentPageIndex],
    ) -> list[CrossDocumentReference]:
        """Resolve references heuristically by matching document type names."""
        references: list[CrossDocumentReference] = []

        type_to_doc: dict[str, str] = {}
        for doc_id, idx in all_indexes.items():
            if doc_id == source_doc_id:
                continue
            # Map normalised doc type fragments to doc_id
            doc_type_lower = idx.document_type.lower().replace("_", " ")
            type_to_doc[doc_type_lower] = doc_id

        for candidate in candidates:
            target_name_lower = candidate["target_name"].lower()
            best_match: Optional[str] = None
            best_score = 0.0

            for doc_type, doc_id in type_to_doc.items():
                # Simple substring matching
                if doc_type in target_name_lower or target_name_lower in doc_type:
                    score = 0.6
                    if best_score < score:
                        best_match = doc_id
                        best_score = score

                # Keyword overlap
                type_words = set(doc_type.split())
                name_words = set(target_name_lower.split())
                overlap = len(type_words & name_words)
                if overlap > 0:
                    score = min(0.8, 0.3 * overlap)
                    if best_score < score:
                        best_match = doc_id
                        best_score = score

            if best_match:
                references.append(CrossDocumentReference(
                    source_document_id=source_doc_id,
                    source_page=candidate["source_page"],
                    reference_text=candidate["reference_text"],
                    target_document_id=best_match,
                    target_node_id="",
                    target_page=None,
                    confidence=best_score,
                ))

        return references
