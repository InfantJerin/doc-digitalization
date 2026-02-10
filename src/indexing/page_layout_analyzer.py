"""Pass 1: Per-page layout extraction using PyMuPDF and pdfplumber.

No LLM calls — pure computational extraction.
"""

from __future__ import annotations

import logging
import re
import statistics
from pathlib import Path
from typing import Optional

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover
    fitz = None

try:
    import pdfplumber
except ImportError:  # pragma: no cover
    pdfplumber = None

from ..core.exceptions import IndexingError
from ..core.models import PageLayout

logger = logging.getLogger(__name__)

# Patterns indicating footnote text at bottom of page
_FOOTNOTE_PATTERN = re.compile(
    r"^\s*(?:\d+|[*†‡§¶])\s+.{10,}", re.MULTILINE
)
_SIGNATURE_PATTERN = re.compile(
    r"(?:IN\s+WITNESS\s+WHEREOF|EXECUTED|SIGNED\s+AND\s+DELIVERED)",
    re.IGNORECASE,
)


class PageLayoutAnalyzer:
    """Extracts structured layout data from each page of a PDF.

    Uses PyMuPDF ``get_text("dict")`` for block-level font analysis and
    pdfplumber ``extract_tables()`` for structured table detection.
    """

    def analyze_document(self, pdf_path: Path | str) -> list[PageLayout]:
        """Analyze all pages in a PDF and return per-page layouts.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            List of ``PageLayout`` objects, one per page.

        Raises:
            IndexingError: When the PDF cannot be processed.
        """
        if fitz is None:
            raise IndexingError("PyMuPDF is required for page layout analysis")

        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise IndexingError(f"PDF not found: {pdf_path}")

        layouts: list[PageLayout] = []
        median_font_size: Optional[float] = None

        try:
            with fitz.open(str(pdf_path)) as doc:
                # First pass: compute median font size across entire document
                all_font_sizes: list[float] = []
                for page in doc:
                    page_dict = page.get_text("dict")
                    for block in page_dict.get("blocks", []):
                        if block.get("type") != 0:  # text block
                            continue
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                size = span.get("size", 0)
                                if size > 0:
                                    all_font_sizes.append(size)

                if all_font_sizes:
                    median_font_size = statistics.median(all_font_sizes)

                # Second pass: extract layout per page
                for page_idx in range(len(doc)):
                    page = doc[page_idx]
                    layout = self._analyze_page(
                        page, page_idx + 1, median_font_size
                    )
                    # Augment with pdfplumber tables
                    tables = self._extract_tables(pdf_path, page_idx)
                    if tables:
                        layout.tables = tables
                    layouts.append(layout)

        except Exception as exc:
            if isinstance(exc, IndexingError):
                raise
            raise IndexingError(f"Failed to analyze {pdf_path.name}: {exc}") from exc

        return layouts

    def _analyze_page(
        self,
        page: "fitz.Page",
        page_number: int,
        median_font_size: Optional[float],
    ) -> PageLayout:
        """Analyze a single page from its PyMuPDF dict representation."""
        page_dict = page.get_text("dict")
        page_height = page_dict.get("height", 792)

        headers: list[str] = []
        paragraphs: list[str] = []
        footnotes: list[str] = []
        images: list[dict] = []
        word_count = 0

        for block in page_dict.get("blocks", []):
            block_type = block.get("type", 0)

            # Image blocks
            if block_type == 1:
                images.append({
                    "bbox": [
                        block.get("bbox", [0, 0, 0, 0])[i] for i in range(4)
                    ],
                })
                continue

            if block_type != 0:
                continue

            block_text_parts: list[str] = []
            max_font_size = 0.0
            is_bold = False
            block_y = block.get("bbox", [0, 0, 0, 0])[1]

            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if not text:
                        continue
                    block_text_parts.append(text)
                    size = span.get("size", 0)
                    if size > max_font_size:
                        max_font_size = size
                    flags = span.get("flags", 0)
                    if flags & 2 ** 4:  # bold flag
                        is_bold = True

            block_text = " ".join(block_text_parts).strip()
            if not block_text:
                continue

            word_count += len(block_text.split())

            # Classify block
            is_footer_region = block_y > page_height * 0.85
            is_header_text = False

            if median_font_size and max_font_size > median_font_size * 1.15:
                is_header_text = True
            elif is_bold and len(block_text) < 200:
                is_header_text = True

            if is_footer_region and _FOOTNOTE_PATTERN.search(block_text):
                footnotes.append(block_text[:500])
            elif is_header_text:
                headers.append(block_text[:300])
            else:
                paragraphs.append(block_text[:2000])

        return PageLayout(
            page_number=page_number,
            headers=headers,
            paragraphs=paragraphs,
            tables=[],
            footnotes=footnotes,
            images=images,
            word_count=word_count,
        )

    def _extract_tables(
        self, pdf_path: Path, page_idx: int
    ) -> list[dict]:
        """Extract tables from a page using pdfplumber."""
        if pdfplumber is None:
            return []

        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                if page_idx >= len(pdf.pages):
                    return []
                page = pdf.pages[page_idx]
                raw_tables = page.extract_tables()
                tables: list[dict] = []
                for table in raw_tables:
                    if not table:
                        continue
                    tables.append({
                        "rows": len(table),
                        "columns": len(table[0]) if table[0] else 0,
                        "data": [
                            [cell or "" for cell in row]
                            for row in table[:50]  # cap rows
                        ],
                    })
                return tables
        except Exception:
            logger.debug(
                "pdfplumber table extraction failed for page %d of %s",
                page_idx + 1,
                pdf_path.name,
            )
            return []
