"""
Review API Routes.

Handles the maker-checker workflow UI endpoints.
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class AttestationRequest(BaseModel):
    """Request to submit an attestation."""
    reviewer_id: str
    reviewer_email: str
    decision: str  # "approved", "rejected", "override"
    fields_attested: list[str]
    overrides: Optional[list[dict]] = None
    comments: Optional[str] = None


class OverrideRequest(BaseModel):
    """Request to override a field value."""
    field_path: str
    original_value: any
    new_value: any
    justification: str


@router.get("")
async def list_review_tasks(
    assignee: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """List review tasks with optional filters."""
    # TODO: Implement database query
    return {
        "tasks": [],
        "total": 0,
        "limit": limit,
        "offset": offset
    }


@router.get("/{task_id}")
async def get_review_task(task_id: str):
    """
    Get complete review data for a task.

    Returns all information needed for the review UI including:
    - Document info
    - Extracted fields (for extraction) or sections (for generation)
    - Citations
    - Attestation status
    """
    from ...workflow.review_handler import ReviewHandler

    handler = ReviewHandler()

    try:
        review_data = await handler.get_review_data(task_id)
        return review_data

    except NotImplementedError:
        raise HTTPException(status_code=501, detail="Database integration pending")
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{task_id}/attest")
async def submit_attestation(task_id: str, request: AttestationRequest):
    """
    Submit an attestation for a review task.

    Reviewers can:
    - Approve individual fields
    - Override values with justification
    - Add comments
    """
    from ...workflow.service import WorkflowService
    from ...core.models import AttestationDecision

    service = WorkflowService()

    try:
        decision = AttestationDecision(request.decision)

        attestation = await service.submit_attestation(
            task_id=task_id,
            reviewer_id=request.reviewer_id,
            reviewer_email=request.reviewer_email,
            decision=decision,
            fields_attested=request.fields_attested,
            overrides=request.overrides,
            comments=request.comments
        )

        return {
            "attestation_id": attestation.id,
            "decision": attestation.decision.value,
            "fields_attested": len(attestation.fields_attested),
            "overrides_count": len(attestation.overrides),
            "timestamp": attestation.timestamp.isoformat()
        }

    except NotImplementedError:
        raise HTTPException(status_code=501, detail="Database integration pending")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{task_id}/summary")
async def get_attestation_summary(task_id: str):
    """Get a summary of attestations for a task."""
    from ...workflow.service import WorkflowService

    service = WorkflowService()

    try:
        summary = await service.get_attestation_summary(task_id)
        return summary

    except NotImplementedError:
        raise HTTPException(status_code=501, detail="Database integration pending")
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{task_id}/fields/{field_path}/citation")
async def get_field_citation(task_id: str, field_path: str):
    """
    Get citation details for a specific field.

    Used to highlight the source in the document viewer.
    """
    from ...workflow.review_handler import ReviewHandler

    handler = ReviewHandler()

    try:
        citation = await handler.get_field_citation(task_id, field_path)
        if not citation:
            raise HTTPException(status_code=404, detail="Citation not found")
        return citation

    except NotImplementedError:
        raise HTTPException(status_code=501, detail="Database integration pending")


@router.get("/{task_id}/revisions")
async def get_revision_history(task_id: str):
    """Get revision history for the run associated with this task."""
    from ...workflow.revision_manager import RevisionManager

    manager = RevisionManager()

    # TODO: Get run details from task, then get revision history
    return {
        "task_id": task_id,
        "revisions": []
    }


@router.get("/{task_id}/revisions/{field_path}")
async def get_field_revision_history(task_id: str, field_path: str):
    """Get revision history for a specific field."""
    from ...workflow.revision_manager import RevisionManager

    manager = RevisionManager()

    # TODO: Implement
    return {
        "field_path": field_path,
        "history": []
    }
