"""Review API routes."""

from __future__ import annotations

from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...core.models import AttestationDecision, ReviewStatus
from ...workflow.review_handler import ReviewHandler
from ...workflow.service import WorkflowService
from ..dependencies import get_review_handler, get_workflow_service

router = APIRouter()


class AttestationRequest(BaseModel):
    reviewer_id: str
    reviewer_email: str
    decision: str
    fields_attested: list[str]
    overrides: Optional[list[dict[str, Any]]] = None
    comments: Optional[str] = None


@router.get("")
async def list_review_tasks(
    assignee: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    service: WorkflowService = Depends(get_workflow_service),
):
    status_enum = ReviewStatus(status) if status else None
    tasks = await service.list_review_tasks(assignee=assignee, status=status_enum)
    sliced = tasks[offset : offset + limit]
    return {
        "tasks": [
            {
                "task_id": task.id,
                "run_id": task.run_id,
                "run_type": task.run_type.value,
                "status": task.status.value,
                "required_attestations": task.required_attestations,
                "current_attestations": len(task.attestations),
                "created_at": task.created_at.isoformat(),
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            }
            for task in sliced
        ],
        "total": len(tasks),
        "limit": limit,
        "offset": offset,
    }


@router.get("/{task_id}")
async def get_review_task(
    task_id: str,
    handler: ReviewHandler = Depends(get_review_handler),
):
    try:
        return await handler.get_review_data(task_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{task_id}/attest")
async def submit_attestation(
    task_id: str,
    request: AttestationRequest,
    service: WorkflowService = Depends(get_workflow_service),
):
    try:
        decision = AttestationDecision(request.decision)
        attestation = await service.submit_attestation(
            task_id=task_id,
            reviewer_id=request.reviewer_id,
            reviewer_email=request.reviewer_email,
            decision=decision,
            fields_attested=request.fields_attested,
            overrides=request.overrides,
            comments=request.comments,
        )
        return {
            "attestation_id": attestation.id,
            "decision": attestation.decision.value,
            "fields_attested": len(attestation.fields_attested),
            "overrides_count": len(attestation.overrides),
            "timestamp": attestation.timestamp.isoformat(),
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{task_id}/summary")
async def get_attestation_summary(
    task_id: str,
    service: WorkflowService = Depends(get_workflow_service),
):
    try:
        return await service.get_attestation_summary(task_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{task_id}/fields/{field_path}/citation")
async def get_field_citation(
    task_id: str,
    field_path: str,
    handler: ReviewHandler = Depends(get_review_handler),
):
    citation = await handler.get_field_citation(task_id, field_path)
    if not citation:
        raise HTTPException(status_code=404, detail="Citation not found")
    return citation


@router.get("/{task_id}/revisions")
async def get_revision_history(task_id: str):
    return {
        "task_id": task_id,
        "revisions": [],
    }


@router.get("/{task_id}/revisions/{field_path}")
async def get_field_revision_history(task_id: str, field_path: str):
    return {
        "task_id": task_id,
        "field_path": field_path,
        "history": [],
    }
