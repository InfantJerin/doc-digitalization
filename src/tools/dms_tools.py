"""DMS tools exposed to the agent runtime."""

from __future__ import annotations

from typing import Optional

from ..integrations.dms_client import DMSClient


class DMSTools:
    """Adapter exposing DMS client operations as typed tool methods."""

    def __init__(self, dms_client: Optional[DMSClient] = None):
        self.dms_client = dms_client or DMSClient()

    async def dms_download(self, document_id: str, target_path: Optional[str] = None) -> str:
        return await self.dms_client.download_document(document_id=document_id, target_path=target_path)

    async def dms_list_documents(
        self,
        deal_id: str,
        document_types: Optional[list[str]] = None,
    ) -> list[dict]:
        return await self.dms_client.get_documents_for_deal(deal_id=deal_id, document_types=document_types)

    async def dms_get_metadata(self, document_id: str) -> dict:
        return await self.dms_client.get_document_metadata(document_id=document_id)
