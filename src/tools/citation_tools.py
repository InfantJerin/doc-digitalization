"""Citation-related tools for extraction orchestration."""

from __future__ import annotations

from ..core.models import Citation
from ..extraction.citation_builder import CitationBuilder


class CitationTools:
    """Wrap citation enhancement and validation capabilities."""

    def __init__(self):
        self.builder = CitationBuilder()

    def citation_find_bbox(self, citation: Citation, pdf_path: str) -> Citation:
        return self.builder.enhance_citation(citation, pdf_path)

    def citation_validate(self, citation: Citation, pdf_path: str) -> dict:
        is_valid, confidence = self.builder.validate_citation(citation, pdf_path)
        return {
            "valid": is_valid,
            "confidence": confidence,
        }
