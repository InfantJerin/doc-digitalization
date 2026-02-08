"""Parse structured agent output into domain models."""

from __future__ import annotations

from ..core.models import BoundingBox, Citation, ExtractedField
from ..core.schemas import ExtractionResultOutput


class ResultParser:
    """Converts ExtractionResultOutput payloads to ExtractedField objects."""

    def parse_fields(self, payload: ExtractionResultOutput) -> list[ExtractedField]:
        fields: list[ExtractedField] = []
        for item in payload.fields:
            citation = None
            if item.citation:
                bbox = None
                if item.citation.bounding_box:
                    bbox = BoundingBox(**item.citation.bounding_box)

                citation = Citation(
                    field_path=item.field_path,
                    document_id=item.citation.document_id or "",
                    page_number=item.citation.page_number,
                    extracted_text=item.citation.extracted_text,
                    confidence=item.citation.confidence,
                    bounding_box=bbox,
                )

            fields.append(
                ExtractedField(
                    field_path=item.field_path,
                    value=item.value,
                    confidence=item.confidence,
                    citation=citation,
                )
            )
        return fields
