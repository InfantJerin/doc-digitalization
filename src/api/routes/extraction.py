"""Extraction API routes wired to AgentOrchestrator-backed service."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...core.schemas import ExtractionCreateRequest, ExtractionCreateResponse
from ...core.models import RunStatus
from ..dependencies import get_extraction_service
from ...extraction.service import ExtractionService

router = APIRouter()


@router.post("", response_model=ExtractionCreateResponse)
async def trigger_extraction(
    request: ExtractionCreateRequest,
    service: ExtractionService = Depends(get_extraction_service),
):
    try:
        run = await service.run_extraction(
            deal_id=request.deal_id,
            pipeline_id=request.pipeline_id,
            document_ids=request.document_ids,
            triggered_by=request.triggered_by,
        )
        return ExtractionCreateResponse(
            run_id=run.id,
            status=run.status.value,
            message="Extraction completed" if run.status != RunStatus.FAILED else "Extraction failed",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{run_id}")
async def get_extraction_run(
    run_id: str,
    service: ExtractionService = Depends(get_extraction_service),
):
    run = await service.get_extraction_run(run_id)
    return {
        "run_id": run.id,
        "deal_id": run.deal_id,
        "pipeline_id": run.pipeline_id,
        "version": run.version,
        "status": run.status.value,
        "document_ids": run.document_ids,
        "agent_session_id": run.agent_session_id,
        "extracted_fields": [
            {
                "field_path": field.field_path,
                "value": field.override_value if field.overridden else field.value,
                "confidence": field.confidence,
                "citation": {
                    "document_id": field.citation.document_id,
                    "page": field.citation.page_number,
                    "text": field.citation.extracted_text,
                }
                if field.citation
                else None,
                "overridden": field.overridden,
                "override_value": field.override_value,
            }
            for field in run.extracted_fields
        ],
        "metadata": run.metadata,
        "created_at": run.created_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "error_message": run.error_message,
    }


@router.get("")
async def list_extractions(
    deal_id: str,
    pipeline_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    service: ExtractionService = Depends(get_extraction_service),
):
    runs = await service.list_extractions_for_deal(
        deal_id=deal_id,
        pipeline_id=pipeline_id,
        limit=limit,
        offset=offset,
    )
    return {
        "extractions": [
            {
                "run_id": run.id,
                "pipeline_id": run.pipeline_id,
                "version": run.version,
                "status": run.status.value,
                "created_at": run.created_at.isoformat(),
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            }
            for run in runs
        ],
        "count": len(runs),
        "limit": limit,
        "offset": offset,
    }


@router.post("/{run_id}/rerun")
async def rerun_extraction(
    run_id: str,
    triggered_by: str,
    service: ExtractionService = Depends(get_extraction_service),
):
    run = await service.rerun_extraction(run_id, triggered_by)
    return {
        "run_id": run.id,
        "version": run.version,
        "status": run.status.value,
    }
