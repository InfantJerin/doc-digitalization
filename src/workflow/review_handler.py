"""
Review Handler.

Handles the review UI data preparation, including side-by-side
document view with citations.
"""

import logging
from typing import Optional, Any
from dataclasses import dataclass

from ..core.models import (
    ReviewTask,
    ExtractionRun,
    GenerationRun,
    ExtractedField,
    GeneratedSection,
    Citation,
    PipelineType,
)

logger = logging.getLogger(__name__)


@dataclass
class FieldReviewData:
    """Data for reviewing a single field."""
    field_path: str
    value: Any
    confidence: float
    citation: Optional[dict]
    attested: bool
    overridden: bool
    override_value: Optional[Any]


@dataclass
class SectionReviewData:
    """Data for reviewing a generated section."""
    section_id: str
    section_name: str
    content: str
    data_points: list[dict]
    has_conflicts: bool
    citations: list[dict]


@dataclass
class ReviewData:
    """Complete review data for the UI."""
    task_id: str
    run_id: str
    run_type: str
    deal_id: str
    pipeline_id: str
    version: int
    status: str
    documents: list[dict]
    fields: Optional[list[FieldReviewData]]  # For extraction
    sections: Optional[list[SectionReviewData]]  # For generation
    attestation_summary: dict


class ReviewHandler:
    """
    Prepares review data for the checker UI.

    Provides:
    - Side-by-side document and extraction view
    - Citation highlighting coordinates
    - Attestation status per field
    - Override history
    """

    async def get_review_data(
        self,
        task_id: str
    ) -> ReviewData:
        """
        Get complete review data for a task.

        This is the main endpoint for the review UI.
        """
        # TODO: Load from database
        raise NotImplementedError("Database integration required")

    async def get_extraction_review_data(
        self,
        run: ExtractionRun,
        task: ReviewTask
    ) -> ReviewData:
        """Prepare review data for an extraction run."""

        # Get document info
        documents = await self._get_documents_info(run.document_ids)

        # Prepare field review data
        fields = [
            FieldReviewData(
                field_path=f.field_path,
                value=f.value,
                confidence=f.confidence,
                citation=self._citation_to_dict(f.citation) if f.citation else None,
                attested=f.attested,
                overridden=f.overridden,
                override_value=f.override_value
            )
            for f in run.extracted_fields
        ]

        # Get attestation summary
        attestation_summary = self._get_attestation_summary(task)

        return ReviewData(
            task_id=task.id,
            run_id=run.id,
            run_type=PipelineType.EXTRACTION.value,
            deal_id=run.deal_id,
            pipeline_id=run.pipeline_id,
            version=run.version,
            status=run.status.value,
            documents=documents,
            fields=fields,
            sections=None,
            attestation_summary=attestation_summary
        )

    async def get_generation_review_data(
        self,
        run: GenerationRun,
        task: ReviewTask
    ) -> ReviewData:
        """Prepare review data for a generation run."""

        # Prepare section review data
        sections = []
        for section in run.sections:
            data_points = []
            has_conflicts = False

            if section.data_points:
                has_conflicts = section.data_points.has_conflicts
                for dp in section.data_points.data_points:
                    data_points.append({
                        "id": dp.data_point_id,
                        "description": dp.description,
                        "status": dp.status.value,
                        "canonical_value": dp.canonical_value,
                        "source_values": [
                            {
                                "source": sv.source_id,
                                "value": sv.value,
                                "confidence": sv.confidence
                            }
                            for sv in dp.source_values
                        ],
                        "conflict_details": dp.conflict_details
                    })

            sections.append(SectionReviewData(
                section_id=section.section_id,
                section_name=section.section_name,
                content=section.content,
                data_points=data_points,
                has_conflicts=has_conflicts,
                citations=[
                    self._citation_to_dict(c) for c in section.citations
                ]
            ))

        # Get attestation summary
        attestation_summary = self._get_attestation_summary(task)

        return ReviewData(
            task_id=task.id,
            run_id=run.id,
            run_type=PipelineType.GENERATION.value,
            deal_id=run.deal_id,
            pipeline_id=run.pipeline_id,
            version=run.version,
            status=run.status.value,
            documents=[],
            fields=None,
            sections=sections,
            attestation_summary=attestation_summary
        )

    async def _get_documents_info(self, document_ids: list[str]) -> list[dict]:
        """Get document info for the review UI."""
        # TODO: Fetch from DMS
        return [
            {
                "id": doc_id,
                "name": f"Document {doc_id}",
                "type": "unknown",
                "page_count": 0,
                "url": f"/api/v1/documents/{doc_id}/view"
            }
            for doc_id in document_ids
        ]

    def _citation_to_dict(self, citation: Citation) -> dict:
        """Convert citation to dict for UI."""
        result = {
            "document_id": citation.document_id,
            "page": citation.page_number,
            "text": citation.extracted_text,
            "confidence": citation.confidence
        }

        if citation.bounding_box:
            result["bounding_box"] = {
                "x": citation.bounding_box.x,
                "y": citation.bounding_box.y,
                "width": citation.bounding_box.width,
                "height": citation.bounding_box.height
            }

        return result

    def _get_attestation_summary(self, task: ReviewTask) -> dict:
        """Get attestation summary for UI."""
        attested_fields = set()
        for attestation in task.attestations:
            attested_fields.update(attestation.fields_attested)

        return {
            "required": task.required_attestations,
            "current": len(task.attestations),
            "is_complete": task.is_fully_attested,
            "attested_fields": list(attested_fields),
            "reviewers": [
                {
                    "email": a.reviewer_email,
                    "decision": a.decision.value,
                    "timestamp": a.timestamp.isoformat()
                }
                for a in task.attestations
            ]
        }

    async def get_field_citation(
        self,
        run_id: str,
        field_path: str
    ) -> Optional[dict]:
        """Get citation details for a specific field."""
        # TODO: Load run and find field
        raise NotImplementedError("Database integration required")

    async def get_document_page(
        self,
        document_id: str,
        page_number: int
    ) -> dict:
        """
        Get document page for display.

        Returns page image URL or content for rendering.
        """
        # TODO: Integrate with DMS
        return {
            "document_id": document_id,
            "page_number": page_number,
            "image_url": f"/api/v1/documents/{document_id}/pages/{page_number}/image",
            "text_content": None  # Optional: extracted text
        }
