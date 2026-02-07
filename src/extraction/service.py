"""
Extraction Service.

Main service for running extraction pipelines.
Orchestrates structure extraction, field extraction, and citation building.
"""

import logging
from datetime import datetime
from typing import Optional
import uuid

from ..core.models import (
    Document,
    DocumentStructure,
    ExtractionRun,
    ExtractedField,
    RunStatus,
    ReviewTask,
    ReviewStatus,
    PipelineType,
)
from ..core.config_loader import (
    ExtractionPipelineConfig,
    load_extraction_config,
)
from ..core.exceptions import (
    ExtractionError,
    PipelineNotFoundError,
    DocumentNotFoundError,
)
from ..integrations.dms_client import DMSClient
from ..integrations.claude_client import ClaudeClient
from .structure_extractor import DocumentStructureExtractor
from .field_extractor import FieldExtractor
from .citation_builder import CitationBuilder

logger = logging.getLogger(__name__)


class ExtractionService:
    """
    Main service for running extraction pipelines.

    Handles:
    - Loading pipeline configuration
    - Fetching documents from DMS
    - Extracting document structure (for large docs)
    - Extracting fields with citations
    - Creating review tasks
    """

    def __init__(
        self,
        dms_client: Optional[DMSClient] = None,
        claude_client: Optional[ClaudeClient] = None
    ):
        self.dms_client = dms_client or DMSClient()
        self.claude_client = claude_client or ClaudeClient()
        self.structure_extractor = DocumentStructureExtractor(self.claude_client)
        self.field_extractor = FieldExtractor(self.claude_client)
        self.citation_builder = CitationBuilder()

    async def run_extraction(
        self,
        deal_id: str,
        pipeline_id: str,
        document_ids: list[str],
        triggered_by: str
    ) -> ExtractionRun:
        """
        Run an extraction pipeline for a deal.

        Args:
            deal_id: The deal identifier
            pipeline_id: The extraction pipeline to run
            document_ids: Specific documents to process
            triggered_by: Who/what triggered this extraction

        Returns:
            ExtractionRun with extracted fields and citations
        """
        logger.info(
            f"Starting extraction: deal={deal_id}, pipeline={pipeline_id}, "
            f"docs={document_ids}, triggered_by={triggered_by}"
        )

        # Create extraction run
        run = ExtractionRun(
            id=str(uuid.uuid4()),
            deal_id=deal_id,
            pipeline_id=pipeline_id,
            version=await self._get_next_version(deal_id, pipeline_id),
            status=RunStatus.PROCESSING,
            document_ids=document_ids,
            triggered_by=triggered_by,
            created_at=datetime.utcnow()
        )

        try:
            # Load pipeline configuration
            config = load_extraction_config(pipeline_id)

            # Process each document
            all_fields = []
            for doc_id in document_ids:
                doc_fields = await self._process_document(doc_id, config)
                all_fields.extend(doc_fields)

            # Deduplicate and merge fields from multiple documents
            merged_fields = self._merge_fields(all_fields)

            run.extracted_fields = merged_fields
            run.status = RunStatus.AWAITING_REVIEW
            run.completed_at = datetime.utcnow()

            # Create review task
            review_task = await self._create_review_task(run, config)

            logger.info(
                f"Extraction completed: run={run.id}, "
                f"fields={len(merged_fields)}, review_task={review_task.id}"
            )

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            run.status = RunStatus.FAILED
            run.error_message = str(e)
            run.completed_at = datetime.utcnow()
            raise ExtractionError(str(e))

        return run

    async def _process_document(
        self,
        document_id: str,
        config: ExtractionPipelineConfig
    ) -> list[ExtractedField]:
        """Process a single document for extraction."""

        # Download document from DMS
        pdf_path = await self.dms_client.download_document(document_id)

        # Check if large document handling is needed
        structure = None
        if config.large_document_handling.enabled:
            structure = await self.structure_extractor.extract(pdf_path)
            logger.info(
                f"Document structure extracted: {structure.mode_used.value}, "
                f"sections={len(structure.get_all_nodes())}"
            )

        # Extract fields
        fields = await self.field_extractor.extract_all_fields(
            pdf_path=pdf_path,
            config=config,
            structure=structure
        )

        # Enhance citations with bounding boxes
        fields = self.citation_builder.enhance_all_citations(fields, pdf_path)

        # Update document ID in citations
        for field in fields:
            if field.citation:
                field.citation.document_id = document_id

        return fields

    def _merge_fields(
        self,
        all_fields: list[ExtractedField]
    ) -> list[ExtractedField]:
        """
        Merge fields from multiple documents.

        For fields extracted from multiple docs:
        - Take the one with highest confidence
        - Keep track of all sources
        """
        field_map: dict[str, ExtractedField] = {}

        for field in all_fields:
            existing = field_map.get(field.field_path)

            if existing is None:
                field_map[field.field_path] = field
            elif field.confidence > existing.confidence:
                # Replace with higher confidence extraction
                field_map[field.field_path] = field

        return list(field_map.values())

    async def _create_review_task(
        self,
        run: ExtractionRun,
        config: ExtractionPipelineConfig
    ) -> ReviewTask:
        """Create a review task for the extraction run."""

        maker_checker = config.workflow.maker_checker

        task = ReviewTask(
            id=str(uuid.uuid4()),
            run_id=run.id,
            run_type=PipelineType.EXTRACTION,
            required_attestations=maker_checker.multi_attest.required_count,
            assignees=maker_checker.multi_attest.roles,
            status=ReviewStatus.PENDING,
            created_at=datetime.utcnow()
        )

        # TODO: Persist review task to database

        return task

    async def _get_next_version(
        self,
        deal_id: str,
        pipeline_id: str
    ) -> int:
        """Get the next version number for a deal/pipeline combination."""
        # TODO: Query database for latest version
        return 1

    async def get_extraction_run(self, run_id: str) -> ExtractionRun:
        """Get an extraction run by ID."""
        # TODO: Implement database lookup
        raise NotImplementedError("Database integration required")

    async def list_extractions_for_deal(
        self,
        deal_id: str,
        pipeline_id: Optional[str] = None
    ) -> list[ExtractionRun]:
        """List all extraction runs for a deal."""
        # TODO: Implement database lookup
        raise NotImplementedError("Database integration required")

    async def rerun_extraction(
        self,
        run_id: str,
        triggered_by: str
    ) -> ExtractionRun:
        """
        Re-run an extraction with the same configuration.
        Creates a new revision.
        """
        original = await self.get_extraction_run(run_id)

        return await self.run_extraction(
            deal_id=original.deal_id,
            pipeline_id=original.pipeline_id,
            document_ids=original.document_ids,
            triggered_by=f"rerun:{triggered_by}"
        )
