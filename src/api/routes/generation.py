"""
Generation API Routes.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import io

router = APIRouter()


class GenerationRequest(BaseModel):
    """Request to trigger a generation."""
    deal_id: str
    pipeline_id: str
    triggered_by: str
    context_vars: Optional[dict] = None


class GenerationResponse(BaseModel):
    """Response from generation trigger."""
    run_id: str
    status: str
    message: str


class RegenerateSectionRequest(BaseModel):
    """Request to regenerate a section."""
    user_feedback: Optional[str] = None


@router.post("", response_model=GenerationResponse)
async def trigger_generation(request: GenerationRequest):
    """
    Trigger a generation pipeline for a deal.

    The generation runs and creates a document based on the
    configured template and data sources.
    """
    from ...generation.service import GenerationService

    service = GenerationService()

    try:
        run = await service.run_generation(
            deal_id=request.deal_id,
            pipeline_id=request.pipeline_id,
            triggered_by=request.triggered_by,
            context_vars=request.context_vars
        )

        return GenerationResponse(
            run_id=run.id,
            status=run.status.value,
            message="Generation completed successfully"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{run_id}")
async def get_generation_run(run_id: str):
    """Get details of a generation run."""
    from ...generation.service import GenerationService

    service = GenerationService()

    try:
        run = await service.get_generation_run(run_id)
        return {
            "run_id": run.id,
            "deal_id": run.deal_id,
            "pipeline_id": run.pipeline_id,
            "version": run.version,
            "status": run.status.value,
            "output_path": run.output_path,
            "output_format": run.output_format,
            "sections": [
                {
                    "section_id": s.section_id,
                    "section_name": s.section_name,
                    "has_conflicts": s.data_points.has_conflicts if s.data_points else False,
                    "conflict_count": s.data_points.conflict_count if s.data_points else 0
                }
                for s in run.sections
            ],
            "created_at": run.created_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None
        }

    except NotImplementedError:
        raise HTTPException(status_code=501, detail="Database integration pending")
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{run_id}/sections/{section_id}")
async def get_section(run_id: str, section_id: str):
    """Get a specific section's content and data points."""
    from ...generation.service import GenerationService

    service = GenerationService()

    try:
        run = await service.get_generation_run(run_id)
        section = next(
            (s for s in run.sections if s.section_id == section_id),
            None
        )

        if not section:
            raise HTTPException(status_code=404, detail="Section not found")

        return {
            "section_id": section.section_id,
            "section_name": section.section_name,
            "content": section.content,
            "data_points": [
                {
                    "id": dp.data_point_id,
                    "description": dp.description,
                    "status": dp.status.value,
                    "canonical_value": dp.canonical_value,
                    "conflict_details": dp.conflict_details,
                    "source_values": [
                        {
                            "source": sv.source_id,
                            "value": sv.value
                        }
                        for sv in dp.source_values
                    ]
                }
                for dp in (section.data_points.data_points if section.data_points else [])
            ],
            "citations": [
                {
                    "document_id": c.document_id,
                    "page": c.page_number,
                    "text": c.extracted_text
                }
                for c in section.citations
            ]
        }

    except NotImplementedError:
        raise HTTPException(status_code=501, detail="Database integration pending")


@router.post("/{run_id}/sections/{section_id}/regenerate")
async def regenerate_section(
    run_id: str,
    section_id: str,
    request: RegenerateSectionRequest
):
    """Regenerate a specific section with optional feedback."""
    from ...generation.service import GenerationService

    service = GenerationService()

    try:
        section = await service.regenerate_section(
            run_id=run_id,
            section_id=section_id,
            user_feedback=request.user_feedback
        )

        return {
            "section_id": section.section_id,
            "section_name": section.section_name,
            "content": section.content,
            "regenerated": section.regenerated
        }

    except NotImplementedError:
        raise HTTPException(status_code=501, detail="Database integration pending")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{run_id}/download")
async def download_document(
    run_id: str,
    format: Optional[str] = None
):
    """Download the generated document."""
    from ...generation.service import GenerationService

    service = GenerationService()

    try:
        content = await service.download_document(run_id, format)

        # Determine content type
        content_type = "application/octet-stream"
        filename = f"document_{run_id}"

        if format == "markdown":
            content_type = "text/markdown"
            filename += ".md"
        elif format == "docx":
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            filename += ".docx"
        elif format == "pdf":
            content_type = "application/pdf"
            filename += ".pdf"

        return StreamingResponse(
            io.BytesIO(content),
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except NotImplementedError:
        raise HTTPException(status_code=501, detail="Database integration pending")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
