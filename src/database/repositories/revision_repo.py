"""Field revision repository."""

from __future__ import annotations

import copy
from collections import defaultdict
from typing import Optional

from ...core.models import FieldRevision, PipelineType


class RevisionRepository:
    """Stores field-level revision history."""

    def __init__(self):
        self._revisions: dict[tuple[str, PipelineType], list[FieldRevision]] = defaultdict(list)

    async def add_revision(self, run_id: str, run_type: PipelineType, revision: FieldRevision) -> None:
        self._revisions[(run_id, run_type)].append(copy.deepcopy(revision))

    async def get_revisions(self, run_id: str, run_type: PipelineType) -> list[FieldRevision]:
        return [copy.deepcopy(r) for r in self._revisions.get((run_id, run_type), [])]

    async def get_field_revisions(
        self,
        run_id: str,
        run_type: PipelineType,
        field_path: str,
    ) -> list[FieldRevision]:
        return [
            revision
            for revision in await self.get_revisions(run_id, run_type)
            if revision.field_path == field_path
        ]
