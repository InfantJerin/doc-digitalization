"""PDF tools exposed to the agent runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    import fitz
except ImportError:  # pragma: no cover
    fitz = None


class PDFTools:
    """Typed helper methods for reading/searching PDF content."""

    def pdf_page_count(self, pdf_path: str) -> int:
        if fitz is None:
            raise RuntimeError("PyMuPDF is required for PDF operations")
        with fitz.open(pdf_path) as doc:
            return len(doc)

    def pdf_read_pages(
        self,
        pdf_path: str,
        pages: list[int],
        max_chars_per_page: int = 6000,
    ) -> list[dict]:
        if fitz is None:
            raise RuntimeError("PyMuPDF is required for PDF operations")

        output = []
        with fitz.open(pdf_path) as doc:
            total = len(doc)
            for page_number in pages:
                if page_number < 1 or page_number > total:
                    continue
                text = doc[page_number - 1].get_text()
                output.append(
                    {
                        "page": page_number,
                        "text": text[:max_chars_per_page],
                    }
                )
        return output

    def pdf_search(
        self,
        pdf_path: str,
        query: str,
        *,
        start_page: int = 1,
        end_page: Optional[int] = None,
        limit: int = 20,
    ) -> list[dict]:
        if fitz is None:
            raise RuntimeError("PyMuPDF is required for PDF operations")

        matches: list[dict] = []
        with fitz.open(pdf_path) as doc:
            last = min(len(doc), end_page or len(doc))
            for page_number in range(max(1, start_page), last + 1):
                page = doc[page_number - 1]
                for rect in page.search_for(query):
                    if len(matches) >= limit:
                        return matches
                    matches.append(
                        {
                            "page": page_number,
                            "bbox": {
                                "x": rect.x0,
                                "y": rect.y0,
                                "width": rect.width,
                                "height": rect.height,
                            },
                        }
                    )
        return matches

    def pdf_get_page_image(self, pdf_path: str, page_number: int, dpi: int = 144) -> bytes:
        if fitz is None:
            raise RuntimeError("PyMuPDF is required for PDF operations")

        with fitz.open(pdf_path) as doc:
            page = doc[page_number - 1]
            pix = page.get_pixmap(dpi=dpi)
            return pix.tobytes("png")
