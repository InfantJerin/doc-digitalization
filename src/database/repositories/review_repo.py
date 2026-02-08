"""Review task repository."""

from __future__ import annotations

import copy
from datetime import datetime
from typing import Optional

from ...core.models import (
    Attestation,
    AttestationDecision,
    FieldOverride,
    PipelineType,
    ReviewStatus,
    ReviewTask,
)
from ..connection import SQLALCHEMY_AVAILABLE
from ..models import AttestationORM, ReviewTaskORM

if SQLALCHEMY_AVAILABLE:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker
else:  # pragma: no cover
    async_sessionmaker = object  # type: ignore[assignment]


class ReviewRepository:
    """Repository for review tasks and attestations."""

    def __init__(self, session_factory: Optional[async_sessionmaker] = None):
        self.session_factory = session_factory
        self._tasks: dict[str, ReviewTask] = {}

    async def create_task(self, task: ReviewTask) -> ReviewTask:
        self._tasks[task.id] = copy.deepcopy(task)
        if self.session_factory and SQLALCHEMY_AVAILABLE:
            await self._upsert_task_sql(task)
        return task

    async def update_task(self, task: ReviewTask) -> ReviewTask:
        self._tasks[task.id] = copy.deepcopy(task)
        if self.session_factory and SQLALCHEMY_AVAILABLE:
            await self._upsert_task_sql(task)
        return task

    async def get_task(self, task_id: str) -> Optional[ReviewTask]:
        existing = self._tasks.get(task_id)
        if existing:
            return copy.deepcopy(existing)

        if self.session_factory and SQLALCHEMY_AVAILABLE:
            task = await self._get_task_sql(task_id)
            if task:
                self._tasks[task_id] = copy.deepcopy(task)
            return task

        return None

    async def list_tasks(
        self,
        assignee: Optional[str] = None,
        status: Optional[ReviewStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ReviewTask]:
        tasks = list(self._tasks.values())
        if assignee:
            tasks = [task for task in tasks if assignee in task.assignees]
        if status:
            tasks = [task for task in tasks if task.status == status]
        tasks.sort(key=lambda task: task.created_at, reverse=True)
        return [copy.deepcopy(task) for task in tasks[offset : offset + limit]]

    async def _upsert_task_sql(self, task: ReviewTask) -> None:
        assert self.session_factory is not None
        async with self.session_factory() as session:
            model = await session.get(ReviewTaskORM, task.id)
            if model is None:
                model = ReviewTaskORM(
                    id=task.id,
                    run_id=task.run_id,
                    run_type=task.run_type.value,
                    assignees=task.assignees,
                    required_attestations=task.required_attestations,
                    status=task.status.value,
                    created_at=task.created_at,
                    completed_at=task.completed_at,
                )
                session.add(model)
            else:
                model.status = task.status.value
                model.assignees = task.assignees
                model.required_attestations = task.required_attestations
                model.completed_at = task.completed_at

            await session.execute(
                AttestationORM.__table__.delete().where(AttestationORM.task_id == task.id)
            )
            for attestation in task.attestations:
                session.add(
                    AttestationORM(
                        id=attestation.id,
                        task_id=task.id,
                        reviewer_id=attestation.reviewer_id,
                        reviewer_email=attestation.reviewer_email,
                        decision=attestation.decision.value,
                        fields_attested=attestation.fields_attested,
                        overrides=[
                            {
                                "field_path": override.field_path,
                                "original_value": override.original_value,
                                "new_value": override.new_value,
                                "justification": override.justification,
                            }
                            for override in attestation.overrides
                        ],
                        comments=attestation.comments,
                        timestamp=attestation.timestamp,
                    )
                )

            await session.commit()

    async def _get_task_sql(self, task_id: str) -> Optional[ReviewTask]:
        assert self.session_factory is not None
        async with self.session_factory() as session:
            model = await session.get(ReviewTaskORM, task_id)
            if model is None:
                return None

            attestation_result = await session.execute(
                select(AttestationORM).where(AttestationORM.task_id == task_id)
            )
            attestations = []
            for row in attestation_result.scalars().all():
                attestations.append(
                    Attestation(
                        id=row.id,
                        reviewer_id=row.reviewer_id,
                        reviewer_email=row.reviewer_email,
                        decision=AttestationDecision(row.decision),
                        fields_attested=row.fields_attested,
                        overrides=[
                            FieldOverride(
                                field_path=override.get("field_path", ""),
                                original_value=override.get("original_value"),
                                new_value=override.get("new_value"),
                                justification=override.get("justification", ""),
                            )
                            for override in row.overrides
                        ],
                        comments=row.comments,
                        timestamp=row.timestamp,
                    )
                )

            return ReviewTask(
                id=model.id,
                run_id=model.run_id,
                run_type=PipelineType(model.run_type),
                assignees=model.assignees,
                required_attestations=model.required_attestations,
                attestations=attestations,
                status=ReviewStatus(model.status),
                created_at=model.created_at,
                completed_at=model.completed_at,
            )
