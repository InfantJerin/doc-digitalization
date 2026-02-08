"""Agent-driven extraction service."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
import uuid

from ..agent.orchestrator import AgentOrchestrator
from ..agent.result_parser import ResultParser
from ..core.config_loader import ConfigLoader, ExtractionPipelineConfig
from ..core.exceptions import ExtractionError
from ..core.models import (
    ExtractionRun,
    PipelineType,
    ReviewStatus,
    ReviewTask,
    RunStatus,
)
from ..database.repositories.extraction_repo import ExtractionRepository
from ..database.repositories.review_repo import ReviewRepository
from ..integrations.dms_client import DMSClient
from .workspace import ExtractionWorkspace, ExtractionWorkspaceManager

logger = logging.getLogger(__name__)


class ExtractionService:
    """Orchestrates extraction runs using the new agent architecture."""

    def __init__(
        self,
        *,
        dms_client: Optional[DMSClient] = None,
        config_loader: Optional[ConfigLoader] = None,
        extraction_repo: Optional[ExtractionRepository] = None,
        review_repo: Optional[ReviewRepository] = None,
        orchestrator: Optional[AgentOrchestrator] = None,
        workspace_manager: Optional[ExtractionWorkspaceManager] = None,
        result_parser: Optional[ResultParser] = None,
    ):
        self.dms_client = dms_client or DMSClient()
        self.config_loader = config_loader or ConfigLoader()
        self.extraction_repo = extraction_repo or ExtractionRepository()
        self.review_repo = review_repo or ReviewRepository()
        self.orchestrator = orchestrator or AgentOrchestrator(config_loader=self.config_loader)
        self.workspace_manager = workspace_manager or ExtractionWorkspaceManager()
        self.result_parser = result_parser or ResultParser()

    async def run_extraction(
        self,
        deal_id: str,
        pipeline_id: str,
        document_ids: list[str],
        triggered_by: str,
        *,
        run_id: Optional[str] = None,
    ) -> ExtractionRun:
        """Create and execute a full extraction run."""
        config = self.config_loader.load_extraction_pipeline(pipeline_id)

        run: Optional[ExtractionRun] = None
        if run_id:
            run = await self.extraction_repo.get_run(run_id)

        if run is None:
            run = ExtractionRun(
                id=run_id or str(uuid.uuid4()),
                deal_id=deal_id,
                pipeline_id=pipeline_id,
                version=await self._get_next_version(deal_id, pipeline_id),
                status=RunStatus.PROCESSING,
                document_ids=document_ids,
                triggered_by=triggered_by,
                created_at=datetime.utcnow(),
            )
            await self.extraction_repo.create_run(run)
        else:
            run.status = RunStatus.PROCESSING
            run.document_ids = document_ids
            run.triggered_by = triggered_by
            run.error_message = None
            run.completed_at = None
            await self.extraction_repo.update_run(run)

        workspace: Optional[ExtractionWorkspace] = None
        try:
            workspace = self.workspace_manager.create(run.id)
            document_paths = await self._download_documents(document_ids, workspace)

            result = await self.orchestrator.run_extraction(
                pipeline_id=pipeline_id,
                workspace_path=workspace.root,
                document_paths=document_paths,
            )
            self.orchestrator.write_debug_prompt(workspace.root, result.prompt)
            self.orchestrator.write_debug_output(workspace.root, result.output)

            run.agent_session_id = result.output.agent_session_id
            run.extracted_fields = self.result_parser.parse_fields(result.output)
            run.completed_at = datetime.utcnow()

            if self._is_auto_approved(run, config):
                run.status = RunStatus.APPROVED
                run.metadata["auto_approved"] = True
            else:
                run.status = RunStatus.AWAITING_REVIEW
                review_task = await self._create_review_task(run, config)
                run.metadata["review_task_id"] = review_task.id

            await self.extraction_repo.update_run(run)
            return run

        except Exception as exc:
            run.status = RunStatus.FAILED
            run.error_message = str(exc)
            run.completed_at = datetime.utcnow()
            await self.extraction_repo.update_run(run)
            logger.exception("Extraction run failed: run_id=%s", run.id)
            raise ExtractionError(str(exc)) from exc
        finally:
            if workspace is not None:
                run.metadata["workspace_path"] = str(workspace.root)

    async def get_extraction_run(self, run_id: str) -> ExtractionRun:
        run = await self.extraction_repo.get_run(run_id)
        if run is None:
            raise ExtractionError(f"Extraction run not found: {run_id}")
        return run

    async def list_extractions_for_deal(
        self,
        deal_id: str,
        pipeline_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ExtractionRun]:
        return await self.extraction_repo.list_runs(
            deal_id=deal_id,
            pipeline_id=pipeline_id,
            limit=limit,
            offset=offset,
        )

    async def rerun_extraction(self, run_id: str, triggered_by: str) -> ExtractionRun:
        original = await self.get_extraction_run(run_id)
        return await self.run_extraction(
            deal_id=original.deal_id,
            pipeline_id=original.pipeline_id,
            document_ids=original.document_ids,
            triggered_by=f"rerun:{triggered_by}",
        )

    async def process_pending_runs(self, limit: int = 10) -> list[ExtractionRun]:
        """Used by worker process to execute pending runs."""
        pending_runs = await self.extraction_repo.list_pending_runs(limit=limit)
        completed: list[ExtractionRun] = []

        for pending in pending_runs:
            if pending.status != RunStatus.PENDING:
                continue

            await self.extraction_repo.mark_processing(pending.id)
            completed.append(
                await self.run_extraction(
                    deal_id=pending.deal_id,
                    pipeline_id=pending.pipeline_id,
                    document_ids=pending.document_ids,
                    triggered_by=pending.triggered_by,
                    run_id=pending.id,
                )
            )

        return completed

    async def _download_documents(
        self,
        document_ids: list[str],
        workspace: ExtractionWorkspace,
    ) -> list[Path]:
        paths: list[Path] = []
        for document_id in document_ids:
            target = workspace.documents_dir / f"{document_id}.pdf"
            downloaded = await self.dms_client.download_document(
                document_id=document_id,
                target_path=str(target),
            )
            paths.append(Path(downloaded))
        return paths

    async def _create_review_task(
        self,
        run: ExtractionRun,
        config: ExtractionPipelineConfig,
    ) -> ReviewTask:
        maker_checker = config.workflow.maker_checker
        task = ReviewTask(
            id=str(uuid.uuid4()),
            run_id=run.id,
            run_type=PipelineType.EXTRACTION,
            assignees=maker_checker.multi_attest.roles,
            required_attestations=maker_checker.multi_attest.required_count,
            status=ReviewStatus.PENDING,
            created_at=datetime.utcnow(),
        )
        await self.review_repo.create_task(task)
        return task

    async def _get_next_version(self, deal_id: str, pipeline_id: str) -> int:
        return await self.extraction_repo.get_next_version(deal_id, pipeline_id)

    def _is_auto_approved(
        self,
        run: ExtractionRun,
        config: ExtractionPipelineConfig,
    ) -> bool:
        if not run.extracted_fields:
            return False

        threshold = config.workflow.maker_checker.auto_approve_threshold
        avg_confidence = sum(field.confidence for field in run.extracted_fields) / len(run.extracted_fields)
        return avg_confidence >= threshold
