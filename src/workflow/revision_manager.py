"""
Revision Manager.

Manages revision history for extraction and generation runs.
Tracks changes across versions and overrides.
"""

import logging
from datetime import datetime
from typing import Optional, Any

from ..core.models import (
    FieldRevision,
    RevisionHistory,
    ExtractionRun,
    GenerationRun,
    PipelineType,
)

logger = logging.getLogger(__name__)


class RevisionManager:
    """
    Manages revision history for runs.

    Tracks:
    - Version history across re-runs
    - Field-level changes between versions
    - Manual overrides with justifications
    - Schema change impacts
    """

    async def get_revision_history(
        self,
        deal_id: str,
        pipeline_id: str,
        run_type: PipelineType
    ) -> RevisionHistory:
        """
        Get complete revision history for a deal/pipeline.

        Returns all versions with their changes.
        """
        # TODO: Query database for all runs
        raise NotImplementedError("Database integration required")

    async def get_field_history(
        self,
        deal_id: str,
        pipeline_id: str,
        field_path: str
    ) -> list[FieldRevision]:
        """
        Get revision history for a specific field.

        Shows how the field value changed across versions.
        """
        history = await self.get_revision_history(
            deal_id, pipeline_id, PipelineType.EXTRACTION
        )
        return history.get_field_history(field_path)

    async def create_revision(
        self,
        run_id: str,
        field_path: str,
        value: Any,
        source: str,
        changed_by: Optional[str] = None,
        justification: Optional[str] = None
    ) -> FieldRevision:
        """
        Create a new revision entry.

        Called when:
        - AI extraction produces new value (source="ai_extracted")
        - User overrides a value (source="manual_override")
        """
        revision = FieldRevision(
            field_path=field_path,
            version=await self._get_next_version(run_id, field_path),
            value=value,
            source=source,
            changed_by=changed_by,
            changed_at=datetime.utcnow(),
            justification=justification
        )

        # TODO: Persist to database
        logger.info(
            f"Created revision: run={run_id}, field={field_path}, "
            f"version={revision.version}, source={source}"
        )

        return revision

    async def _get_next_version(self, run_id: str, field_path: str) -> int:
        """Get next version number for a field."""
        # TODO: Query database
        return 1

    async def compare_versions(
        self,
        deal_id: str,
        pipeline_id: str,
        version1: int,
        version2: int
    ) -> dict:
        """
        Compare two versions of a run.

        Returns diff showing:
        - Added fields
        - Removed fields
        - Changed fields with old/new values
        """
        # TODO: Load both versions and compare
        raise NotImplementedError("Database integration required")

    async def get_latest_version(
        self,
        deal_id: str,
        pipeline_id: str
    ) -> int:
        """Get the latest version number for a deal/pipeline."""
        # TODO: Query database
        return 1

    async def trigger_schema_revision(
        self,
        pipeline_id: str,
        old_schema: dict,
        new_schema: dict
    ) -> list[str]:
        """
        Handle schema change.

        Identifies affected deals and marks them for re-extraction.
        Returns list of deal IDs that need re-extraction.
        """
        # Compare schemas to find changes
        added_fields = set(new_schema.keys()) - set(old_schema.keys())
        removed_fields = set(old_schema.keys()) - set(new_schema.keys())

        # Find modified fields
        modified_fields = []
        for field in set(new_schema.keys()) & set(old_schema.keys()):
            if new_schema[field] != old_schema[field]:
                modified_fields.append(field)

        logger.info(
            f"Schema change for {pipeline_id}: "
            f"added={added_fields}, removed={removed_fields}, "
            f"modified={modified_fields}"
        )

        # TODO: Query database for affected deals
        affected_deals = []

        return affected_deals

    def format_revision_summary(
        self,
        history: RevisionHistory
    ) -> list[dict]:
        """
        Format revision history for UI display.

        Groups revisions by version and shows timeline.
        """
        # Group by field
        by_field = {}
        for rev in history.revisions:
            if rev.field_path not in by_field:
                by_field[rev.field_path] = []
            by_field[rev.field_path].append(rev)

        # Sort each field's history by version
        summary = []
        for field_path, revisions in by_field.items():
            revisions.sort(key=lambda r: r.version)
            summary.append({
                "field": field_path,
                "current_version": revisions[-1].version if revisions else 0,
                "current_value": revisions[-1].value if revisions else None,
                "history": [
                    {
                        "version": r.version,
                        "value": r.value,
                        "source": r.source,
                        "changed_by": r.changed_by,
                        "changed_at": r.changed_at.isoformat(),
                        "justification": r.justification
                    }
                    for r in revisions
                ]
            })

        return summary
