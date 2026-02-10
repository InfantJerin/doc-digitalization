"""Per-document indexer — orchestrates the three indexing passes."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from ..core.exceptions import IndexingError
from ..core.models import DocumentPageIndex, DocumentStructure
from ..extraction.structure_extractor import (
    DocumentStructureExtractor,
    StructureExtractionConfig,
)
from ..integrations.llm_base import LLMClientProtocol
from .keyword_extractor import KeywordExtractor
from .page_layout_analyzer import PageLayoutAnalyzer

logger = logging.getLogger(__name__)


class DocumentIndexer:
    """Builds a complete per-document index.

    Orchestrates:
    1. ``PageLayoutAnalyzer`` — layout per page (no LLM)
    2. ``DocumentStructureExtractor`` — reuses existing 4-strategy extractor
    3. ``KeywordExtractor`` — term extraction (regex + optional LLM)
    """

    def __init__(
        self,
        *,
        llm_client: Optional[LLMClientProtocol] = None,
        layout_analyzer: Optional[PageLayoutAnalyzer] = None,
        structure_extractor: Optional[DocumentStructureExtractor] = None,
        keyword_extractor: Optional[KeywordExtractor] = None,
        max_keywords: int = 500,
    ):
        self.llm_client = llm_client
        self.layout_analyzer = layout_analyzer or PageLayoutAnalyzer()
        self.structure_extractor = structure_extractor or DocumentStructureExtractor(
            claude_client=llm_client,
            config=StructureExtractionConfig(
                generate_summaries=bool(llm_client),
            ),
        )
        self.keyword_extractor = keyword_extractor or KeywordExtractor(
            llm_client=llm_client,
            max_keywords=max_keywords,
        )

    async def build_index(
        self,
        pdf_path: Path | str,
        document_id: str,
        document_type: str = "",
        *,
        use_llm_keywords: bool = False,
        skip_layout_analysis: bool = False,
    ) -> DocumentPageIndex:
        """Build a complete index for a single document.

        Args:
            pdf_path: Path to the PDF file.
            document_id: Unique identifier for the document.
            document_type: Type of document (e.g. "credit_agreement").
            use_llm_keywords: Whether to use LLM for keyword normalization.
            skip_layout_analysis: Skip layout analysis (useful for testing).

        Returns:
            A fully populated ``DocumentPageIndex``.

        Raises:
            IndexingError: When indexing fails.
        """
        pdf_path = Path(pdf_path)
        logger.info("Building index for document %s (%s)", document_id, pdf_path.name)

        # Pass 1: Page layout analysis
        if skip_layout_analysis:
            page_layouts = []
        else:
            try:
                page_layouts = self.layout_analyzer.analyze_document(pdf_path)
            except Exception as exc:
                raise IndexingError(
                    f"Layout analysis failed for {document_id}: {exc}"
                ) from exc

        total_pages = len(page_layouts)

        # Pass 2: Structure extraction (reuses existing extractor)
        structure: Optional[DocumentStructure] = None
        if self.structure_extractor:
            try:
                structure = await self.structure_extractor.extract(str(pdf_path))
                if structure:
                    structure.document_id = document_id
            except Exception:
                logger.warning(
                    "Structure extraction failed for %s, continuing without structure",
                    document_id,
                )

        # Pass 3: Keyword extraction
        try:
            keyword_index = await self.keyword_extractor.extract_keywords(
                page_layouts,
                structure,
                use_llm=use_llm_keywords,
            )
        except Exception:
            logger.warning(
                "Keyword extraction failed for %s, continuing with empty index",
                document_id,
            )
            keyword_index = []

        return DocumentPageIndex(
            document_id=document_id,
            document_type=document_type,
            total_pages=total_pages,
            structure=structure,
            page_layouts=page_layouts,
            keyword_index=keyword_index,
        )
