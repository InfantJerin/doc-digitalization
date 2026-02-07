"""
Workflow Service.

Main service for managing the review workflow, attestations, and approvals.
"""

import logging
from datetime import datetime
from typing import Optional
import uuid

from ..core.models import (
    ReviewTask,
    ReviewStatus,
    Attestation,
    AttestationDecision,
    FieldOverride,
    ExtractionRun,
    GenerationRun,
    PipelineType,
    RunStatus,
)
from ..core.exceptions import (
    WorkflowError,
    ReviewTaskNotFoundError,
    InvalidOverrideError,
    JustificationRequiredError,
)

logger = logging.getLogger(__name__)


class WorkflowService:
    """
    Manages the maker-checker workflow.

    Handles:
    - Review task assignment
    - Field attestations
    - Overrides with justification
    - Approval flow
    - Post-sink delivery on approval
    """

    def __init__(
        self,
        min_justification_length: int = 20,
        require_justification_for_override: bool = True
    ):
        self.min_justification_length = min_justification_length
        self.require_justification_for_override = require_justification_for_override

    async def create_review_task(
        self,
        run_id: str,
        run_type: PipelineType,
        required_attestations: int = 1,
        assignees: Optional[list[str]] = None
    ) -> ReviewTask:
        """Create a new review task for a run."""
        task = ReviewTask(
            id=str(uuid.uuid4()),
            run_id=run_id,
            run_type=run_type,
            required_attestations=required_attestations,
            assignees=assignees or [],
            status=ReviewStatus.PENDING,
            created_at=datetime.utcnow()
        )

        # TODO: Persist to database
        logger.info(f"Created review task: {task.id} for run {run_id}")

        return task

    async def get_review_task(self, task_id: str) -> ReviewTask:
        """Get a review task by ID."""
        # TODO: Implement database lookup
        raise NotImplementedError("Database integration required")

    async def list_review_tasks(
        self,
        assignee: Optional[str] = None,
        status: Optional[ReviewStatus] = None
    ) -> list[ReviewTask]:
        """List review tasks with optional filters."""
        # TODO: Implement database lookup
        raise NotImplementedError("Database integration required")

    async def submit_attestation(
        self,
        task_id: str,
        reviewer_id: str,
        reviewer_email: str,
        decision: AttestationDecision,
        fields_attested: list[str],
        overrides: Optional[list[dict]] = None,
        comments: Optional[str] = None
    ) -> Attestation:
        """
        Submit an attestation for a review task.

        Args:
            task_id: The review task ID
            reviewer_id: The reviewer's user ID
            reviewer_email: The reviewer's email
            decision: APPROVED, REJECTED, or OVERRIDE
            fields_attested: List of field paths being attested
            overrides: Optional list of field overrides
            comments: Optional comments

        Returns:
            The created attestation
        """
        task = await self.get_review_task(task_id)

        if task.status == ReviewStatus.COMPLETED:
            raise WorkflowError("Review task already completed")

        # Process overrides
        field_overrides = []
        if overrides:
            for override_data in overrides:
                field_override = self._validate_override(override_data)
                field_overrides.append(field_override)

        # Create attestation
        attestation = Attestation(
            id=str(uuid.uuid4()),
            reviewer_id=reviewer_id,
            reviewer_email=reviewer_email,
            decision=decision,
            fields_attested=fields_attested,
            overrides=field_overrides,
            comments=comments or "",
            timestamp=datetime.utcnow()
        )

        # Add to task
        task.attestations.append(attestation)
        task.status = ReviewStatus.IN_PROGRESS

        # Check if fully attested
        if task.is_fully_attested:
            task.status = ReviewStatus.COMPLETED
            task.completed_at = datetime.utcnow()

            # Apply overrides to the run
            await self._apply_overrides(task)

            # Trigger post-sink delivery
            await self._trigger_post_sink(task)

        # TODO: Persist changes
        logger.info(
            f"Attestation submitted: task={task_id}, reviewer={reviewer_email}, "
            f"decision={decision.value}"
        )

        return attestation

    def _validate_override(self, override_data: dict) -> FieldOverride:
        """Validate an override request."""
        field_path = override_data.get("field_path")
        if not field_path:
            raise InvalidOverrideError("field_path is required")

        justification = override_data.get("justification", "")
        if self.require_justification_for_override:
            if not justification or len(justification) < self.min_justification_length:
                raise JustificationRequiredError(field_path)

        return FieldOverride(
            field_path=field_path,
            original_value=override_data.get("original_value"),
            new_value=override_data.get("new_value"),
            justification=justification
        )

    async def _apply_overrides(self, task: ReviewTask):
        """Apply all overrides from attestations to the run."""
        all_overrides = []
        for attestation in task.attestations:
            all_overrides.extend(attestation.overrides)

        if not all_overrides:
            return

        # TODO: Load run from database and apply overrides
        logger.info(f"Applying {len(all_overrides)} overrides to run {task.run_id}")

    async def _trigger_post_sink(self, task: ReviewTask):
        """Trigger post-sink delivery after approval."""
        # TODO: Implement webhook delivery
        logger.info(f"Triggering post-sink for run {task.run_id}")

    async def get_attestation_summary(self, task_id: str) -> dict:
        """Get a summary of attestations for a task."""
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
                    "by": attestation.reviewer_email
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
                    "id": a.id,
                    "reviewer": a.reviewer_email,
                    "decision": a.decision.value,
                    "timestamp": a.timestamp.isoformat(),
                    "fields_count": len(a.fields_attested),
                    "overrides_count": len(a.overrides)
                }
                for a in task.attestations
            ]
        }
