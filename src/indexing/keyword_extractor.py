"""Pass 2a: Keyword and term extraction from document pages.

Hybrid approach: regex-based candidate extraction + optional LLM normalization.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Optional

from ..core.models import (
    DocumentStructure,
    KeywordEntry,
    PageLayout,
    TermType,
)
from ..integrations.llm_base import LLMClientProtocol

logger = logging.getLogger(__name__)

# --- Regex patterns for candidate extraction ---

# Defined terms: quoted or capitalised multi-word phrases
_DEFINED_TERM_PATTERN = re.compile(
    r'"([A-Z][A-Za-z\s\-]{2,50})"'
)

# Section references: Section 1.01, Article IV, Schedule A
_SECTION_REF_PATTERN = re.compile(
    r"(?:Section|Article|Schedule|Exhibit|Appendix|Annex)\s+[\dIVXivx]+(?:\.\d+)?(?:\([a-z]\))?",
    re.IGNORECASE,
)

# Financial metrics: EBITDA, Leverage Ratio, Interest Coverage, etc.
_FINANCIAL_METRIC_PATTERN = re.compile(
    r"\b(?:EBITDA|Adjusted EBITDA|Net Income|Total Debt|Senior Debt|"
    r"Leverage Ratio|Interest Coverage Ratio|Fixed Charge Coverage|"
    r"Debt Service Coverage|Total Net Leverage|Secured Net Leverage|"
    r"Minimum Liquidity|Current Ratio|Quick Ratio|Tangible Net Worth|"
    r"Capital Expenditures|Consolidated Net Income|"
    r"Applicable (?:Margin|Rate|Percentage)|"
    r"Base Rate|SOFR|Term SOFR|LIBOR|Prime Rate|"
    r"Eurocurrency Rate)\b",
    re.IGNORECASE,
)

# Entity-like patterns (Inc., LLC, Corp., etc.)
_ENTITY_PATTERN = re.compile(
    r"\b([A-Z][A-Za-z\s&,.']+(?:Inc\.|LLC|Corp\.|L\.P\.|N\.A\.|Ltd\.))",
)

# Date patterns
_DATE_PATTERN = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+\d{1,2},?\s+\d{4}\b"
)


class KeywordExtractor:
    """Extracts keyword entries from page layouts and document structure.

    Operates in two modes:
    - **Regex-only** (no LLM): fast, deterministic candidate extraction
    - **LLM-assisted** (optional): normalizes synonyms and groups terms
    """

    def __init__(
        self,
        *,
        llm_client: Optional[LLMClientProtocol] = None,
        max_keywords: int = 500,
    ):
        self.llm_client = llm_client
        self.max_keywords = max_keywords

    async def extract_keywords(
        self,
        page_layouts: list[PageLayout],
        structure: Optional[DocumentStructure] = None,
        *,
        use_llm: bool = False,
    ) -> list[KeywordEntry]:
        """Extract keywords from page layouts.

        Args:
            page_layouts: Analyzed page layouts.
            structure: Optional document structure for section mapping.
            use_llm: Whether to use LLM for synonym normalization.

        Returns:
            Deduplicated list of ``KeywordEntry`` capped at ``max_keywords``.
        """
        # Build page -> section mapping from structure
        page_section_map = self._build_page_section_map(structure)

        # Collect candidates from each page
        candidates: dict[str, KeywordEntry] = {}

        for layout in page_layouts:
            page_text = " ".join(layout.headers + layout.paragraphs)
            page_num = layout.page_number
            sections = page_section_map.get(page_num, [])

            self._extract_from_text(
                page_text, page_num, sections, candidates
            )

        # Detect definition pages
        definitions_pages = self._find_definitions_pages(structure)
        if definitions_pages:
            self._mark_definition_pages(candidates, page_layouts, definitions_pages)

        # Optional LLM normalization
        if use_llm and self.llm_client:
            candidates = await self._llm_normalize(candidates)

        # Sort by frequency (number of pages), then cap
        entries = sorted(
            candidates.values(),
            key=lambda e: len(e.pages),
            reverse=True,
        )
        return entries[: self.max_keywords]

    def _extract_from_text(
        self,
        text: str,
        page_num: int,
        sections: list[str],
        candidates: dict[str, KeywordEntry],
    ) -> None:
        """Extract regex candidates from a page text block."""

        # Defined terms
        for match in _DEFINED_TERM_PATTERN.finditer(text):
            term = match.group(1).strip()
            self._add_candidate(
                candidates, term, page_num, sections, TermType.DEFINED_TERM
            )

        # Section references
        for match in _SECTION_REF_PATTERN.finditer(text):
            term = match.group(0).strip()
            self._add_candidate(
                candidates, term, page_num, sections, TermType.SECTION_REFERENCE
            )

        # Financial metrics
        for match in _FINANCIAL_METRIC_PATTERN.finditer(text):
            term = match.group(0).strip()
            self._add_candidate(
                candidates, term, page_num, sections, TermType.FINANCIAL_METRIC
            )

        # Entities
        for match in _ENTITY_PATTERN.finditer(text):
            term = match.group(1).strip()
            if len(term) > 5:
                self._add_candidate(
                    candidates, term, page_num, sections, TermType.ENTITY
                )

        # Dates
        for match in _DATE_PATTERN.finditer(text):
            term = match.group(0).strip()
            self._add_candidate(
                candidates, term, page_num, sections, TermType.DATE
            )

    def _add_candidate(
        self,
        candidates: dict[str, KeywordEntry],
        term: str,
        page_num: int,
        sections: list[str],
        term_type: TermType,
    ) -> None:
        """Add or update a candidate keyword entry."""
        canonical = term.strip().lower()
        if canonical in candidates:
            entry = candidates[canonical]
            if page_num not in entry.pages:
                entry.pages.append(page_num)
            for sec in sections:
                if sec not in entry.sections:
                    entry.sections.append(sec)
        else:
            candidates[canonical] = KeywordEntry(
                term=term,
                canonical_term=canonical,
                pages=[page_num],
                sections=list(sections),
                term_type=term_type,
            )

    def _build_page_section_map(
        self, structure: Optional[DocumentStructure]
    ) -> dict[int, list[str]]:
        """Map page numbers to section titles from document structure."""
        mapping: dict[int, list[str]] = defaultdict(list)
        if not structure:
            return mapping

        for node in structure.get_all_nodes():
            end = node.end_page or node.start_page
            for page in range(node.start_page, end + 1):
                if node.title not in mapping[page]:
                    mapping[page].append(node.title)
        return mapping

    def _find_definitions_pages(
        self, structure: Optional[DocumentStructure]
    ) -> list[int]:
        """Find page ranges for definitions sections."""
        if not structure:
            return []

        pages: list[int] = []
        for node in structure.get_all_nodes():
            if "definition" in node.title.lower():
                end = node.end_page or node.start_page
                pages.extend(range(node.start_page, end + 1))
        return pages

    def _mark_definition_pages(
        self,
        candidates: dict[str, KeywordEntry],
        page_layouts: list[PageLayout],
        definitions_pages: list[int],
    ) -> None:
        """Mark definition_page for terms found in definitions sections."""
        for canonical, entry in candidates.items():
            for page_num in entry.pages:
                if page_num in definitions_pages:
                    entry.definition_page = page_num
                    break

    async def _llm_normalize(
        self, candidates: dict[str, KeywordEntry]
    ) -> dict[str, KeywordEntry]:
        """Use LLM to normalize and group synonymous terms."""
        if not self.llm_client or len(candidates) < 2:
            return candidates

        # Only send a sample to the LLM to keep cost low
        sample_terms = list(candidates.keys())[:100]
        prompt = (
            "You are a financial document term normalizer.\n"
            "Given these terms extracted from a credit agreement, "
            "group synonyms and return a JSON mapping of "
            "original_term -> canonical_term.\n"
            "Only group terms that are truly synonymous.\n"
            f"Terms: {sample_terms}\n"
            "Return JSON: {{\"mappings\": {{\"original\": \"canonical\", ...}}}}"
        )

        try:
            result = await self.llm_client.query_json(prompt=prompt, max_tokens=2000)
            mappings = result.get("mappings", {})

            for original, canonical in mappings.items():
                original_lower = original.lower()
                canonical_lower = canonical.lower()
                if original_lower in candidates and canonical_lower != original_lower:
                    entry = candidates[original_lower]
                    entry.canonical_term = canonical_lower
        except Exception:
            logger.warning("LLM keyword normalization failed, using regex-only results")

        return candidates
