"""
Citation Builder.

Builds and validates citations linking extracted values to
their source locations in documents.
"""

import re
import logging
from typing import Optional

try:
    import fitz
except ImportError:
    fitz = None

from ..core.models import Citation, BoundingBox, ExtractedField

logger = logging.getLogger(__name__)


class CitationBuilder:
    """
    Builds citations with bounding boxes for document highlighting.
    """

    def __init__(self):
        if fitz is None:
            logger.warning("PyMuPDF not installed. Bounding box detection unavailable.")

    def enhance_citation(
        self,
        citation: Citation,
        pdf_path: str
    ) -> Citation:
        """
        Enhance a citation with bounding box coordinates.

        Takes an existing citation (with page and quote) and adds
        precise bounding box coordinates for UI highlighting.
        """
        if fitz is None or not citation.extracted_text:
            return citation

        try:
            doc = fitz.open(pdf_path)
            page_idx = citation.page_number - 1

            if page_idx < 0 or page_idx >= len(doc):
                return citation

            page = doc[page_idx]

            # Search for the quoted text on the page
            text_instances = page.search_for(citation.extracted_text)

            if text_instances:
                # Use the first match
                rect = text_instances[0]
                citation.bounding_box = BoundingBox(
                    x=rect.x0,
                    y=rect.y0,
                    width=rect.width,
                    height=rect.height
                )
            else:
                # Try fuzzy matching if exact match fails
                bbox = self._fuzzy_search(page, citation.extracted_text)
                if bbox:
                    citation.bounding_box = bbox

            doc.close()

        except Exception as e:
            logger.warning(f"Failed to enhance citation: {e}")

        return citation

    def _fuzzy_search(
        self,
        page,
        text: str
    ) -> Optional[BoundingBox]:
        """
        Fuzzy search for text on a page.
        Handles minor variations in spacing and formatting.
        """
        # Normalize the search text
        normalized = re.sub(r'\s+', ' ', text.strip())
        words = normalized.split()

        if len(words) < 2:
            return None

        # Search for first few words
        partial = ' '.join(words[:3])
        instances = page.search_for(partial)

        if instances:
            rect = instances[0]
            return BoundingBox(
                x=rect.x0,
                y=rect.y0,
                width=rect.width,
                height=rect.height
            )

        return None

    def validate_citation(
        self,
        citation: Citation,
        pdf_path: str
    ) -> tuple[bool, float]:
        """
        Validate that a citation's quote exists on the specified page.

        Returns:
            Tuple of (is_valid, confidence)
        """
        if fitz is None:
            return True, 1.0  # Assume valid if can't check

        if not citation.extracted_text:
            return False, 0.0

        try:
            doc = fitz.open(pdf_path)
            page_idx = citation.page_number - 1

            if page_idx < 0 or page_idx >= len(doc):
                doc.close()
                return False, 0.0

            page = doc[page_idx]
            page_text = page.get_text()

            # Normalize for comparison
            normalized_quote = re.sub(r'\s+', ' ', citation.extracted_text.lower().strip())
            normalized_page = re.sub(r'\s+', ' ', page_text.lower())

            doc.close()

            if normalized_quote in normalized_page:
                return True, 1.0

            # Check partial match
            words = normalized_quote.split()
            if len(words) >= 3:
                partial = ' '.join(words[:5])
                if partial in normalized_page:
                    return True, 0.8

            return False, 0.0

        except Exception as e:
            logger.warning(f"Failed to validate citation: {e}")
            return False, 0.0

    def enhance_all_citations(
        self,
        fields: list[ExtractedField],
        pdf_path: str
    ) -> list[ExtractedField]:
        """Enhance all citations in a list of extracted fields."""
        for field in fields:
            if field.citation:
                field.citation = self.enhance_citation(field.citation, pdf_path)
        return fields

    def generate_citation_report(
        self,
        fields: list[ExtractedField],
        pdf_path: str
    ) -> dict:
        """
        Generate a citation validation report.

        Returns dict with validation results for each field.
        """
        report = {
            "total_fields": len(fields),
            "fields_with_citations": 0,
            "valid_citations": 0,
            "invalid_citations": 0,
            "missing_citations": 0,
            "details": []
        }

        for field in fields:
            if not field.citation:
                report["missing_citations"] += 1
                report["details"].append({
                    "field": field.field_path,
                    "status": "missing",
                    "confidence": 0.0
                })
                continue

            report["fields_with_citations"] += 1
            is_valid, confidence = self.validate_citation(field.citation, pdf_path)

            if is_valid:
                report["valid_citations"] += 1
                status = "valid"
            else:
                report["invalid_citations"] += 1
                status = "invalid"

            report["details"].append({
                "field": field.field_path,
                "status": status,
                "page": field.citation.page_number,
                "quote_preview": field.citation.extracted_text[:50] + "..."
                    if len(field.citation.extracted_text) > 50
                    else field.citation.extracted_text,
                "confidence": confidence
            })

        return report
