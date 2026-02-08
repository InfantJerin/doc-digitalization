"""Workflow service wired to repositories."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
import uuid

from ..core.models import (
    Attestation,
    AttestationDecision,
    FieldOverride,
    PipelineType,
    ReviewStatus,
    ReviewTask,
)
from ..core.exceptions import (
    JustificationRequiredError,
    ReviewTaskNotFoundError,
    WorkflowError,
)
from ..database.repositories.extraction_repo import ExtractionRepository
from ..database.repositories.review_repo import ReviewRepository

logger = logging.getLogger(__name__)


class WorkflowService:
    """Manages review/attestation workflow backed by repositories."""

    def __init__(
        self,
        *,
        review_repo: Optional[ReviewRepository] = None,
        extraction_repo: Optional[ExtractionRepository] = None,
        min_justification_length: int = 20,
        require_justification_for_override: bool = True,
    ):
        self.review_repo = review_repo or ReviewRepository()
        self.extraction_repo = extraction_repo or ExtractionRepository()
        self.min_justification_length = min_justification_length
        self.require_justification_for_override = require_justification_for_override

    async def create_review_task(
        self,
        run_id: str,
        run_type: PipelineType,
        required_attestations: int = 1,
        assignees: Optional[list[str]] = None,
    ) -> ReviewTask:
        task = ReviewTask(
            id=str(uuid.uuid4()),
            run_id=run_id,
            run_type=run_type,
            required_attestations=required_attestations,
            assignees=assignees or [],
            status=ReviewStatus.PENDING,
            created_at=datetime.utcnow(),
        )
        return await self.review_repo.create_task(task)

    async def get_review_task(self, task_id: str) -> ReviewTask:
        task = await self.review_repo.get_task(task_id)
        if not task:
            raise ReviewTaskNotFoundError(task_id)
        return task

    async def list_review_tasks(
        self,
        assignee: Optional[str] = None,
        status: Optional[ReviewStatus] = None,
    ) -> list[ReviewTask]:
        return await self.review_repo.list_tasks(assignee=assignee, status=status)

    async def submit_attestation(
        self,
        task_id: str,
        reviewer_id: str,
        reviewer_email: str,
        decision: AttestationDecision,
        fields_attested: list[str],
        overrides: Optional[list[dict]] = None,
        comments: Optional[str] = None,
    ) -> Attestation:
        task = await self.get_review_task(task_id)

        if task.status == ReviewStatus.COMPLETED:
            raise WorkflowError("Review task already completed")

        validated_overrides = [self._validate_override(payload) for payload in (overrides or [])]

        attestation = Attestation(
            id=str(uuid.uuid4()),
            reviewer_id=reviewer_id,
            reviewer_email=reviewer_email,
            decision=decision,
            fields_attested=fields_attested,
            overrides=validated_overrides,
            comments=comments or "",
            timestamp=datetime.utcnow(),
        )

        task.attestations.append(attestation)
        task.status = ReviewStatus.IN_PROGRESS

        if task.is_fully_attested:
            task.status = ReviewStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            await self._apply_overrides(task)
            await self._trigger_post_sink(task)

        await self.review_repo.update_task(task)
        return attestation

    async def get_attestation_summary(self, task_id: str) -> dict:
        task = await self.get_review_task(task_id)

        attested_fields = set()
        overridden_fields = {}

        for attestation in task.attestations:
            attested_fields.update(attestation.fields_attested)
            for override in attestation.overrides:
                overridden_fields[override.field_path] = {
                    "original": override.original_value,
                    "new": override.new_value,
                    "justification": override.justification,
                    "by": attestation.reviewer_email,
                }

        return {
            "task_id": task_id,
            "status": task.status.value,
            "required_attestations": task.required_attestations,
            "current_attestations": len(task.attestations),
            "is_complete": task.is_fully_attested,
            "attested_fields": list(attested_fields),
            "overridden_fields": overridden_fields,
            "attestations": [
                {
                    "id": item.id,
                    "reviewer": item.reviewer_email,
                    "decision": item.decision.value,
                    "timestamp": item.timestamp.isoformat(),
                    "fields_count": len(item.fields_attested),
                    "overrides_count": len(item.overrides),
                }
                for item in task.attestations
            ],
        }

    def _validate_override(self, payload: dict) -> FieldOverride:
        field_path = payload.get("field_path", "").strip()
        if not field_path:
            raise WorkflowError("Override requires field_path")

        justification = str(payload.get("justification", ""))
        if self.require_justification_for_override and len(justification) < self.min_justification_length:
            raise JustificationRequiredError(field_path)

        return FieldOverride(
            field_path=field_path,
            original_value=payload.get("original_value"),
            new_value=payload.get("new_value"),
            justification=justification,
        )

    async def _apply_overrides(self, task: ReviewTask) -> None:
        if task.run_type != PipelineType.EXTRACTION:
            return

        run = await self.extraction_repo.get_run(task.run_id)
        if not run:
            logger.warning("Run not found for override application: %s", task.run_id)
            return

        for attestation in task.attestations:
            for override in attestation.overrides:
                field = run.get_field(override.field_path)
                if not field:
                    continue
                field.overridden = True
                field.override_value = override.new_value
                field.override_justification = override.justification

        await self.extraction_repo.update_run(run)

    async def _trigger_post_sink(self, task: ReviewTask) -> None:
        logger.info("Post-sink trigger placeholder for task=%s", task.id)
