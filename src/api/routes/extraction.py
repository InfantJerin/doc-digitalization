"""
Extraction API Routes.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

router = APIRouter()


class ExtractionRequest(BaseModel):
    """Request to trigger an extraction."""
    deal_id: str
    pipeline_id: str
    document_ids: list[str]
    triggered_by: str


class ExtractionResponse(BaseModel):
    """Response from extraction trigger."""
    run_id: str
    status: str
    message: str


@router.post("", response_model=ExtractionResponse)
async def trigger_extraction(
    request: ExtractionRequest,
    background_tasks: BackgroundTasks
):
    """
    Trigger an extraction pipeline for a deal.

    The extraction runs asynchronously. Use GET /extractions/{run_id}
    to check status and retrieve results.
    """
    from ...extraction.service import ExtractionService

    service = ExtractionService()

    try:
        run = await service.run_extraction(
            deal_id=request.deal_id,
            pipeline_id=request.pipeline_id,
            document_ids=request.document_ids,
            triggered_by=request.triggered_by
        )

        return ExtractionResponse(
            run_id=run.id,
            status=run.status.value,
            message="Extraction completed successfully"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{run_id}")
async def get_extraction_run(run_id: str):
    """Get details of an extraction run."""
    from ...extraction.service import ExtractionService

    service = ExtractionService()

    try:
        run = await service.get_extraction_run(run_id)
        return {
            "run_id": run.id,
            "deal_id": run.deal_id,
            "pipeline_id": run.pipeline_id,
            "version": run.version,
            "status": run.status.value,
            "document_ids": run.document_ids,
            "extracted_fields": [
                {
                    "field_path": f.field_path,
                    "value": f.value,
                    "confidence": f.confidence,
                    "citation": {
                        "document_id": f.citation.document_id,
                        "page": f.citation.page_number,
                        "text": f.citation.extracted_text
                    } if f.citation else None
                }
                for f in run.extracted_fields
            ],
            "created_at": run.created_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None
        }

    except NotImplementedError:
        raise HTTPException(status_code=501, detail="Database integration pending")
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("")
async def list_extractions(
    deal_id: Optional[str] = None,
    pipeline_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """List extraction runs with optional filters."""
    # TODO: Implement database query
    return {
        "extractions": [],
        "total": 0,
        "limit": limit,
        "offset": offset
    }


@router.post("/{run_id}/rerun")
async def rerun_extraction(run_id: str, triggered_by: str):
    """Re-run an extraction, creating a new revision."""
    from ...extraction.service import ExtractionService

    service = ExtractionService()

    try:
        new_run = await service.rerun_extraction(run_id, triggered_by)
        return {
            "run_id": new_run.id,
            "version": new_run.version,
            "status": new_run.status.value
        }

    except NotImplementedError:
        raise HTTPException(status_code=501, detail="Database integration pending")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
