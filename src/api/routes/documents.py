"""
Document API Routes.

Proxy endpoints for document viewing in the review UI.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

router = APIRouter()


@router.get("/{document_id}")
async def get_document_metadata(document_id: str):
    """Get document metadata."""
    from ...integrations.dms_client import DMSClient

    client = DMSClient()

    try:
        metadata = await client.get_document_metadata(document_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="Document not found")
        return metadata

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}/pages/{page_number}/image")
async def get_page_image(document_id: str, page_number: int):
    """
    Get a document page as an image for the review UI.

    Returns PNG image of the page for display with citation highlighting.
    """
    from ...integrations.dms_client import DMSClient

    client = DMSClient()

    try:
        image_bytes = await client.get_page_image(document_id, page_number)
        return Response(
            content=image_bytes,
            media_type="image/png"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}/view")
async def get_document_viewer_url(document_id: str):
    """
    Get URL for viewing the document.

    Returns information needed to display the document in the UI.
    """
    from ...integrations.dms_client import DMSClient

    client = DMSClient()

    try:
        metadata = await client.get_document_metadata(document_id)

        return {
            "document_id": document_id,
            "name": metadata.get("name", f"Document {document_id}"),
            "page_count": metadata.get("page_count", 0),
            "pages_url": f"/api/v1/documents/{document_id}/pages",
            "download_url": f"/api/v1/documents/{document_id}/download"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}/download")
async def download_document(document_id: str):
    """Download the original document."""
    from ...integrations.dms_client import DMSClient

    client = DMSClient()

    try:
        path = await client.download_document(document_id)

        with open(path, "rb") as f:
            content = f.read()

        return Response(
            content=content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={document_id}.pdf"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
