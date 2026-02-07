"""
Document Management System Client.

Interface for document storage and retrieval.
"""

import logging
import os
from pathlib import Path
from typing import Optional
import httpx

logger = logging.getLogger(__name__)


class DMSClient:
    """
    Client for the Document Management System.

    Provides:
    - Document upload/download
    - Document listing by deal
    - Document metadata
    - Content extraction
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        temp_dir: Optional[str] = None
    ):
        self.base_url = base_url or os.getenv("DMS_BASE_URL", "http://localhost:8080")
        self.api_key = api_key or os.getenv("DMS_API_KEY", "")
        self.temp_dir = Path(temp_dir or "/tmp/doc_digitalization")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.http_client = httpx.AsyncClient(timeout=60.0)

    async def get_documents_for_deal(
        self,
        deal_id: str,
        document_types: Optional[list[str]] = None
    ) -> list[dict]:
        """
        Get all documents for a deal.

        Args:
            deal_id: The deal identifier
            document_types: Optional filter by document types

        Returns:
            List of document metadata dicts
        """
        try:
            params = {"deal_id": deal_id}
            if document_types:
                params["types"] = ",".join(document_types)

            response = await self.http_client.get(
                f"{self.base_url}/api/v1/deals/{deal_id}/documents",
                params=params,
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json().get("documents", [])

        except httpx.HTTPError as e:
            logger.error(f"Failed to get documents for deal {deal_id}: {e}")
            # Return empty list for now - in production, might want to raise
            return []

    async def download_document(
        self,
        document_id: str,
        target_path: Optional[str] = None
    ) -> str:
        """
        Download a document to local storage.

        Args:
            document_id: The document identifier
            target_path: Optional specific path, otherwise uses temp dir

        Returns:
            Path to the downloaded file
        """
        if target_path is None:
            target_path = str(self.temp_dir / f"{document_id}.pdf")

        try:
            response = await self.http_client.get(
                f"{self.base_url}/api/v1/documents/{document_id}/download",
                headers=self._get_headers()
            )
            response.raise_for_status()

            with open(target_path, "wb") as f:
                f.write(response.content)

            logger.info(f"Downloaded document {document_id} to {target_path}")
            return target_path

        except httpx.HTTPError as e:
            logger.error(f"Failed to download document {document_id}: {e}")
            raise

    async def get_document_content(
        self,
        document_id: str
    ) -> str:
        """
        Get extracted text content of a document.

        Args:
            document_id: The document identifier

        Returns:
            Extracted text content
        """
        try:
            response = await self.http_client.get(
                f"{self.base_url}/api/v1/documents/{document_id}/content",
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json().get("content", "")

        except httpx.HTTPError as e:
            logger.error(f"Failed to get content for document {document_id}: {e}")
            return ""

    async def get_document_metadata(
        self,
        document_id: str
    ) -> dict:
        """
        Get document metadata.

        Args:
            document_id: The document identifier

        Returns:
            Document metadata dict
        """
        try:
            response = await self.http_client.get(
                f"{self.base_url}/api/v1/documents/{document_id}",
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Failed to get metadata for document {document_id}: {e}")
            return {}

    async def upload_document(
        self,
        deal_id: str,
        file_path: str,
        document_type: str,
        metadata: Optional[dict] = None
    ) -> str:
        """
        Upload a document to DMS.

        Args:
            deal_id: The deal to attach the document to
            file_path: Path to the file to upload
            document_type: Type of document
            metadata: Optional additional metadata

        Returns:
            Document ID of the uploaded document
        """
        try:
            with open(file_path, "rb") as f:
                files = {"file": (Path(file_path).name, f)}
                data = {
                    "deal_id": deal_id,
                    "document_type": document_type,
                    "metadata": metadata or {}
                }

                response = await self.http_client.post(
                    f"{self.base_url}/api/v1/documents",
                    files=files,
                    data=data,
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json().get("document_id")

        except httpx.HTTPError as e:
            logger.error(f"Failed to upload document: {e}")
            raise

    async def get_page_image(
        self,
        document_id: str,
        page_number: int
    ) -> bytes:
        """
        Get a page as an image (for UI display).

        Args:
            document_id: The document identifier
            page_number: Page number (1-indexed)

        Returns:
            Image bytes (PNG)
        """
        try:
            response = await self.http_client.get(
                f"{self.base_url}/api/v1/documents/{document_id}/pages/{page_number}/image",
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.content

        except httpx.HTTPError as e:
            logger.error(f"Failed to get page image: {e}")
            raise

    def _get_headers(self) -> dict:
        """Get request headers."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()
