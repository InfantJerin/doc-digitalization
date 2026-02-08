"""Extraction run repository."""

from __future__ import annotations

import copy
from collections import defaultdict
from datetime import datetime
from typing import Optional

from ...core.models import (
    BoundingBox,
    Citation,
    ExtractedField,
    ExtractionRun,
    RunStatus,
)
from ..connection import SQLALCHEMY_AVAILABLE
from ..models import ExtractedFieldORM, ExtractionRunORM

if SQLALCHEMY_AVAILABLE:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker
else:  # pragma: no cover
    async_sessionmaker = object  # type: ignore[assignment]


class ExtractionRepository:
    """Repository for extraction runs and extracted fields."""

    def __init__(self, session_factory: Optional[async_sessionmaker] = None):
        self.session_factory = session_factory
        self._runs: dict[str, ExtractionRun] = {}
        self._by_deal_pipeline: dict[tuple[str, str], list[str]] = defaultdict(list)

    async def create_run(self, run: ExtractionRun) -> ExtractionRun:
        if self.session_factory and SQLALCHEMY_AVAILABLE:
            await self._create_run_sql(run)
        self._upsert_memory(run)
        return run

    async def update_run(self, run: ExtractionRun) -> ExtractionRun:
        if self.session_factory and SQLALCHEMY_AVAILABLE:
            await self._update_run_sql(run)
        self._upsert_memory(run)
        return run

    async def get_run(self, run_id: str) -> Optional[ExtractionRun]:
        if run_id in self._runs:
            return copy.deepcopy(self._runs[run_id])

        if self.session_factory and SQLALCHEMY_AVAILABLE:
            run = await self._get_run_sql(run_id)
            if run:
                self._upsert_memory(run)
                return run
        return None

    async def list_runs(
        self,
        deal_id: str,
        pipeline_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ExtractionRun]:
        key_runs: list[ExtractionRun] = []

        if pipeline_id:
            run_ids = self._by_deal_pipeline.get((deal_id, pipeline_id), [])
            key_runs = [self._runs[run_id] for run_id in run_ids if run_id in self._runs]
        else:
            for (candidate_deal, _), run_ids in self._by_deal_pipeline.items():
                if candidate_deal != deal_id:
                    continue
                key_runs.extend(self._runs[run_id] for run_id in run_ids if run_id in self._runs)

        key_runs.sort(key=lambda run: run.created_at, reverse=True)
        sliced = key_runs[offset : offset + limit]
        return [copy.deepcopy(run) for run in sliced]

    async def get_next_version(self, deal_id: str, pipeline_id: str) -> int:
        run_ids = self._by_deal_pipeline.get((deal_id, pipeline_id), [])
        if not run_ids:
            return 1

        latest = max(
            (self._runs[run_id].version for run_id in run_ids if run_id in self._runs),
            default=0,
        )
        return latest + 1

    async def list_pending_runs(self, limit: int = 20) -> list[ExtractionRun]:
        pending = [run for run in self._runs.values() if run.status == RunStatus.PENDING]
        pending.sort(key=lambda run: run.created_at)
        return [copy.deepcopy(run) for run in pending[:limit]]

    async def mark_processing(self, run_id: str) -> Optional[ExtractionRun]:
        run = await self.get_run(run_id)
        if not run:
            return None
        run.status = RunStatus.PROCESSING
        await self.update_run(run)
        return run

    def _upsert_memory(self, run: ExtractionRun) -> None:
        self._runs[run.id] = copy.deepcopy(run)
        key = (run.deal_id, run.pipeline_id)
        if run.id not in self._by_deal_pipeline[key]:
            self._by_deal_pipeline[key].append(run.id)

    async def _create_run_sql(self, run: ExtractionRun) -> None:
        assert self.session_factory is not None
        async with self.session_factory() as session:
            model = ExtractionRunORM(
                id=run.id,
                deal_id=run.deal_id,
                pipeline_id=run.pipeline_id,
                version=run.version,
                status=run.status.value,
                document_ids=run.document_ids,
                agent_session_id=run.agent_session_id,
                triggered_by=run.triggered_by,
                created_at=run.created_at,
                completed_at=run.completed_at,
                error_message=run.error_message,
                metadata_json=run.metadata,
            )
            session.add(model)
            for field in run.extracted_fields:
                session.add(
                    ExtractedFieldORM(
                        run_id=run.id,
                        field_path=field.field_path,
                        value_json=field.value,
                        confidence=field.confidence,
                        citation_json=self._citation_to_dict(field.citation),
                        attested=field.attested,
                        attested_by=field.attested_by,
                        overridden=field.overridden,
                        override_value_json=field.override_value,
                        override_justification=field.override_justification,
                    )
                )
            await session.commit()

    async def _update_run_sql(self, run: ExtractionRun) -> None:
        assert self.session_factory is not None
        async with self.session_factory() as session:
            model = await session.get(ExtractionRunORM, run.id)
            if model is None:
                await self._create_run_sql(run)
                return

            model.status = run.status.value
            model.completed_at = run.completed_at
            model.error_message = run.error_message
            model.agent_session_id = run.agent_session_id
            model.metadata_json = run.metadata
            await session.execute(
                ExtractedFieldORM.__table__.delete().where(ExtractedFieldORM.run_id == run.id)
            )
            for field in run.extracted_fields:
                session.add(
                    ExtractedFieldORM(
                        run_id=run.id,
                        field_path=field.field_path,
                        value_json=field.value,
                        confidence=field.confidence,
                        citation_json=self._citation_to_dict(field.citation),
                        attested=field.attested,
                        attested_by=field.attested_by,
                        overridden=field.overridden,
                        override_value_json=field.override_value,
                        override_justification=field.override_justification,
                    )
                )
            await session.commit()

    async def _get_run_sql(self, run_id: str) -> Optional[ExtractionRun]:
        assert self.session_factory is not None
        async with self.session_factory() as session:
            model = await session.get(ExtractionRunORM, run_id)
            if model is None:
                return None

            fields_result = await session.execute(
                select(ExtractedFieldORM).where(ExtractedFieldORM.run_id == run_id)
            )
            fields = []
            for row in fields_result.scalars().all():
                fields.append(
                    ExtractedField(
                        field_path=row.field_path,
                        value=row.value_json,
                        confidence=row.confidence,
                        citation=self._citation_from_dict(row.citation_json),
                        attested=row.attested,
                        attested_by=row.attested_by,
                        overridden=row.overridden,
                        override_value=row.override_value_json,
                        override_justification=row.override_justification,
                    )
                )

            return ExtractionRun(
                id=model.id,
                deal_id=model.deal_id,
                pipeline_id=model.pipeline_id,
                version=model.version,
                status=RunStatus(model.status),
                document_ids=model.document_ids,
                extracted_fields=fields,
                agent_session_id=model.agent_session_id,
                triggered_by=model.triggered_by,
                created_at=model.created_at,
                completed_at=model.completed_at,
                error_message=model.error_message,
                metadata=model.metadata_json or {},
            )

    def _citation_to_dict(self, citation: Optional[Citation]) -> Optional[dict]:
        if citation is None:
            return None
        payload = {
            "field_path": citation.field_path,
            "document_id": citation.document_id,
            "page_number": citation.page_number,
            "extracted_text": citation.extracted_text,
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

    def _citation_from_dict(self, payload: Optional[dict]) -> Optional[Citation]:
        if payload is None:
            return None
        bbox = payload.get("bounding_box")
        return Citation(
            field_path=payload.get("field_path", ""),
            document_id=payload.get("document_id", ""),
            page_number=payload.get("page_number", 0),
            extracted_text=payload.get("extracted_text", ""),
            confidence=payload.get("confidence", 0.0),
            bounding_box=BoundingBox(**bbox) if bbox else None,
        )
