"""
Data Gatherer.

Gathers data from multiple sources (APIs, DMS, extraction pipelines, databases)
for document generation.
"""

import logging
from typing import Any, Optional
import httpx

from ..core.models import Citation
from ..core.config_loader import (
    GenerationPipelineConfig,
    DataSourceConfig,
    DataSourceType,
)
from ..core.exceptions import DataGatheringError
from ..integrations.dms_client import DMSClient
from .data_point_validator import DataContext

logger = logging.getLogger(__name__)


class DataGatherer:
    """
    Gathers data from configured sources for document generation.

    Supports:
    - API endpoints (REST)
    - Document Management System (documents for extraction)
    - Extraction pipelines (previous extraction results)
    - Databases (direct queries)
    """

    def __init__(
        self,
        dms_client: Optional[DMSClient] = None,
        http_client: Optional[httpx.AsyncClient] = None
    ):
        self.dms_client = dms_client or DMSClient()
        self.http_client = http_client or httpx.AsyncClient(timeout=30.0)

    async def gather_all_data(
        self,
        deal_id: str,
        config: GenerationPipelineConfig,
        context_vars: Optional[dict] = None
    ) -> DataContext:
        """
        Gather data from all configured sources.

        Args:
            deal_id: The deal identifier
            config: Generation pipeline configuration
            context_vars: Variables for template substitution (e.g., company_id)

        Returns:
            DataContext with data from all sources
        """
        context_vars = context_vars or {}
        context_vars["deal_id"] = deal_id

        sources_data = {}
        citations = {}

        for source_id, source_config in config.data_sources.items():
            try:
                data, source_citations = await self._gather_from_source(
                    source_id,
                    source_config,
                    context_vars
                )
                sources_data[source_id] = data
                if source_citations:
                    citations[source_id] = source_citations

                logger.info(f"Gathered data from source: {source_id}")

            except Exception as e:
                logger.error(f"Failed to gather data from {source_id}: {e}")
                raise DataGatheringError(source_id, str(e))

        return DataContext(sources=sources_data, citations=citations)

    async def _gather_from_source(
        self,
        source_id: str,
        config: DataSourceConfig,
        context_vars: dict
    ) -> tuple[Any, list[Citation]]:
        """Gather data from a single source."""

        match config.type:
            case DataSourceType.API:
                return await self._gather_from_api(config, context_vars)
            case DataSourceType.DMS:
                return await self._gather_from_dms(config, context_vars)
            case DataSourceType.EXTRACTION_PIPELINE:
                return await self._gather_from_extraction(config, context_vars)
            case DataSourceType.DATABASE:
                return await self._gather_from_database(config, context_vars)
            case _:
                raise DataGatheringError(source_id, f"Unknown source type: {config.type}")

    async def _gather_from_api(
        self,
        config: DataSourceConfig,
        context_vars: dict
    ) -> tuple[dict, list[Citation]]:
        """Gather data from an API endpoint."""

        if not config.endpoint:
            raise DataGatheringError("api", "No endpoint configured")

        # Substitute context variables in endpoint
        endpoint = config.endpoint.format(**context_vars)

        # Add authentication if configured
        headers = {}
        if config.auth == "oauth2":
            # TODO: Implement OAuth2 token retrieval
            headers["Authorization"] = "Bearer <token>"

        try:
            response = await self.http_client.get(endpoint, headers=headers)
            response.raise_for_status()
            return response.json(), []

        except httpx.HTTPError as e:
            raise DataGatheringError("api", f"HTTP error: {e}")

    async def _gather_from_dms(
        self,
        config: DataSourceConfig,
        context_vars: dict
    ) -> tuple[dict, list[Citation]]:
        """
        Gather data from DMS documents.

        This fetches documents and extracts content/data from them.
        """
        deal_id = context_vars.get("deal_id")
        if not deal_id:
            raise DataGatheringError("dms", "No deal_id in context")

        # Get documents of specified types
        documents = await self.dms_client.get_documents_for_deal(
            deal_id=deal_id,
            document_types=config.document_types
        )

        # Extract content from documents
        # This would typically use the extraction pipeline
        extracted_data = {}
        citations = []

        for doc in documents:
            # If an extraction schema is specified, use it
            if config.extraction_schema:
                # Run extraction with schema
                # TODO: Integrate with extraction service
                pass
            else:
                # Just get raw content
                content = await self.dms_client.get_document_content(doc["id"])
                extracted_data[doc["type"]] = content

        return extracted_data, citations

    async def _gather_from_extraction(
        self,
        config: DataSourceConfig,
        context_vars: dict
    ) -> tuple[dict, list[Citation]]:
        """Gather data from a previous extraction pipeline run."""

        if not config.pipeline_id:
            raise DataGatheringError("extraction", "No pipeline_id configured")

        deal_id = context_vars.get("deal_id")
        if not deal_id:
            raise DataGatheringError("extraction", "No deal_id in context")

        # TODO: Query extraction service for latest run
        # For now, return placeholder
        return {
            "_source": "extraction_pipeline",
            "pipeline_id": config.pipeline_id,
            "deal_id": deal_id
        }, []

    async def _gather_from_database(
        self,
        config: DataSourceConfig,
        context_vars: dict
    ) -> tuple[dict, list[Citation]]:
        """Gather data from a database query."""

        if not config.query:
            raise DataGatheringError("database", "No query configured")

        # TODO: Implement database connection and query execution
        # For now, return placeholder
        return {
            "_source": "database",
            "connection": config.connection,
            "query": config.query
        }, []

    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()
