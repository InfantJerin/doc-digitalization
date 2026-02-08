"""Review data assembler for the checker UI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from ..core.models import (
    Citation,
    ExtractionRun,
    GeneratedSection,
    GenerationRun,
    PipelineType,
    ReviewTask,
)
from ..core.exceptions import ReviewTaskNotFoundError
from ..database.repositories.extraction_repo import ExtractionRepository
from ..database.repositories.review_repo import ReviewRepository


@dataclass
class FieldReviewData:
    field_path: str
    value: Any
    confidence: float
    citation: Optional[dict]
    attested: bool
    overridden: bool
    override_value: Optional[Any]


@dataclass
class SectionReviewData:
    section_id: str
    section_name: str
    content: str
    data_points: list[dict]
    has_conflicts: bool
    citations: list[dict]


@dataclass
class ReviewData:
    task_id: str
    run_id: str
    run_type: str
    deal_id: str
    pipeline_id: str
    version: int
    status: str
    documents: list[dict]
    fields: Optional[list[FieldReviewData]]
    sections: Optional[list[SectionReviewData]]
    attestation_summary: dict


class ReviewHandler:
    """Builds payloads used by review UI endpoints."""

    def __init__(
        self,
        *,
        review_repo: Optional[ReviewRepository] = None,
        extraction_repo: Optional[ExtractionRepository] = None,
    ):
        self.review_repo = review_repo or ReviewRepository()
        self.extraction_repo = extraction_repo or ExtractionRepository()

    async def get_review_data(self, task_id: str) -> ReviewData:
        task = await self.review_repo.get_task(task_id)
        if not task:
            raise ReviewTaskNotFoundError(task_id)

        if task.run_type == PipelineType.EXTRACTION:
            run = await self.extraction_repo.get_run(task.run_id)
            if not run:
                raise ReviewTaskNotFoundError(task_id)
            return await self.get_extraction_review_data(run, task)

        raise NotImplementedError("Generation review payload is not migrated yet")

    async def get_extraction_review_data(
        self,
        run: ExtractionRun,
        task: ReviewTask,
    ) -> ReviewData:
        documents = [
            {
                "id": document_id,
                "name": f"Document {document_id}",
                "type": "unknown",
                "url": f"/api/v1/documents/{document_id}/view",
            }
            for document_id in run.document_ids
        ]

        fields = [
            FieldReviewData(
                field_path=field.field_path,
                value=field.override_value if field.overridden else field.value,
                confidence=field.confidence,
                citation=self._citation_to_dict(field.citation) if field.citation else None,
                attested=field.attested,
                overridden=field.overridden,
                override_value=field.override_value,
            )
            for field in run.extracted_fields
        ]

        return ReviewData(
            task_id=task.id,
            run_id=run.id,
            run_type=task.run_type.value,
            deal_id=run.deal_id,
            pipeline_id=run.pipeline_id,
            version=run.version,
            status=task.status.value,
            documents=documents,
            fields=fields,
            sections=None,
            attestation_summary=self._attestation_summary(task),
        )

    async def get_field_citation(self, task_id: str, field_path: str) -> Optional[dict]:
        task = await self.review_repo.get_task(task_id)
        if not task or task.run_type != PipelineType.EXTRACTION:
            return None

        run = await self.extraction_repo.get_run(task.run_id)
        if not run:
            return None

        field = run.get_field(field_path)
        if not field or not field.citation:
            return None
        return self._citation_to_dict(field.citation)

    def _citation_to_dict(self, citation: Citation) -> dict:
        payload = {
            "document_id": citation.document_id,
            "page": citation.page_number,
            "text": citation.extracted_text,
            "confidence": citation.confidence,
        }
        if citation.bounding_box:
            payload["bounding_box"] = {
                "x": citation.bounding_box.x,
                "y": citation.bounding_box.y,
                "width": citation.bounding_box.width,
                "height": citation.bounding_box.height,
            }
        return payload

    def _attestation_summary(self, task: ReviewTask) -> dict:
        attested_fields = set()
        for attestation in task.attestations:
            attested_fields.update(attestation.fields_attested)

        return {
            "required": task.required_attestations,
            "current": len(task.attestations),
            "is_complete": task.is_fully_attested,
            "attested_fields": sorted(attested_fields),
            "reviewers": [
                {
                    "email": item.reviewer_email,
                    "decision": item.decision.value,
                    "timestamp": item.timestamp.isoformat(),
                }
                for item in task.attestations
            ],
        }
