"""
Generation Service.

Main service for running generation pipelines.
Orchestrates data gathering, section generation, and document assembly.
"""

import logging
from datetime import datetime
from typing import Optional
import uuid

from ..core.models import (
    GenerationRun,
    GeneratedSection,
    RunStatus,
    ReviewTask,
    ReviewStatus,
    PipelineType,
)
from ..core.config_loader import (
    GenerationPipelineConfig,
    load_generation_config,
)
from ..core.exceptions import GenerationError, PipelineNotFoundError
from ..integrations.dms_client import DMSClient
from ..integrations.llm_base import LLMClientProtocol
from ..integrations.llm_factory import get_llm_client
from .data_gatherer import DataGatherer
from .section_generator import SectionGenerator
from .document_assembler import DocumentAssembler

logger = logging.getLogger(__name__)


class GenerationService:
    """
    Main service for running generation pipelines.

    Handles:
    - Loading pipeline configuration
    - Gathering data from multiple sources
    - Validating data points across sources
    - Generating document sections
    - Assembling final documents
    - Creating review tasks
    """

    def __init__(
        self,
        dms_client: Optional[DMSClient] = None,
        claude_client: Optional[LLMClientProtocol] = None,
        output_dir: Optional[str] = None
    ):
        self.dms_client = dms_client or DMSClient()
        self.claude_client = claude_client or get_llm_client()
        self.data_gatherer = DataGatherer(dms_client=self.dms_client)
        self.section_generator = SectionGenerator(claude_client=self.claude_client)
        self.document_assembler = DocumentAssembler(output_dir=output_dir)

    async def run_generation(
        self,
        deal_id: str,
        pipeline_id: str,
        triggered_by: str,
        context_vars: Optional[dict] = None
    ) -> GenerationRun:
        """
        Run a generation pipeline for a deal.

        Args:
            deal_id: The deal identifier
            pipeline_id: The generation pipeline to run
            triggered_by: Who/what triggered this generation
            context_vars: Additional context variables for data sources

        Returns:
            GenerationRun with generated sections
        """
        logger.info(
            f"Starting generation: deal={deal_id}, pipeline={pipeline_id}, "
            f"triggered_by={triggered_by}"
        )

        # Create generation run
        run = GenerationRun(
            id=str(uuid.uuid4()),
            deal_id=deal_id,
            pipeline_id=pipeline_id,
            version=await self._get_next_version(deal_id, pipeline_id),
            status=RunStatus.PROCESSING,
            triggered_by=triggered_by,
            created_at=datetime.utcnow()
        )

        try:
            # Load pipeline configuration
            config = load_generation_config(pipeline_id)
            run.output_format = config.output.format

            # Step 1: Gather data from all sources
            data_context = await self.data_gatherer.gather_all_data(
                deal_id=deal_id,
                config=config,
                context_vars=context_vars
            )
            logger.info(f"Data gathered from {len(data_context.sources)} sources")

            # Step 2: Generate each section
            sections = []
            style_config = {
                "tone": config.template.style.tone,
                "perspective": config.template.style.perspective
            }

            for section_config in config.template.sections:
                section = await self.section_generator.generate_section(
                    section_config=section_config,
                    data_context=data_context,
                    style_config=style_config
                )
                sections.append(section)

                # Handle subsections
                for subsection_config in section_config.subsections:
                    subsection = await self.section_generator.generate_section(
                        section_config=subsection_config,
                        data_context=data_context,
                        style_config=style_config
                    )
                    sections.append(subsection)

            run.sections = sections

            # Step 3: Assemble document
            output_path = await self.document_assembler.assemble(run, config)
            run.output_path = output_path

            # Step 4: Update status and create review task
            run.status = RunStatus.AWAITING_REVIEW
            run.completed_at = datetime.utcnow()

            if config.workflow.review_required:
                review_task = await self._create_review_task(run, config)
                logger.info(f"Review task created: {review_task.id}")

            logger.info(
                f"Generation completed: run={run.id}, "
                f"sections={len(sections)}, output={output_path}"
            )

        except Exception as e:
            logger.error(f"Generation failed: {e}")
            run.status = RunStatus.FAILED
            run.error_message = str(e)
            run.completed_at = datetime.utcnow()
            raise GenerationError(str(e))

        return run

    async def regenerate_section(
        self,
        run_id: str,
        section_id: str,
        user_feedback: Optional[str] = None
    ) -> GeneratedSection:
        """
        Regenerate a specific section with optional user feedback.

        Args:
            run_id: The generation run ID
            section_id: The section to regenerate
            user_feedback: Optional feedback for regeneration

        Returns:
            The regenerated section
        """
        # TODO: Load run from database
        run = await self.get_generation_run(run_id)
        config = load_generation_config(run.pipeline_id)

        # Find section config
        section_config = None
        for sc in config.template.sections:
            if sc.id == section_id:
                section_config = sc
                break
            for ssc in sc.subsections:
                if ssc.id == section_id:
                    section_config = ssc
                    break

        if not section_config:
            raise GenerationError(f"Section not found: {section_id}")

        # Find existing section
        existing_section = None
        for s in run.sections:
            if s.section_id == section_id:
                existing_section = s
                break

        # Re-gather data
        data_context = await self.data_gatherer.gather_all_data(
            deal_id=run.deal_id,
            config=config
        )

        # Regenerate
        new_section = await self.section_generator.regenerate_section(
            section=existing_section,
            section_config=section_config,
            data_context=data_context,
            user_feedback=user_feedback,
            style_config={
                "tone": config.template.style.tone,
                "perspective": config.template.style.perspective
            }
        )

        # Update run with new section
        for i, s in enumerate(run.sections):
            if s.section_id == section_id:
                run.sections[i] = new_section
                break

        # TODO: Persist updated run

        return new_section

    async def _create_review_task(
        self,
        run: GenerationRun,
        config: GenerationPipelineConfig
    ) -> ReviewTask:
        """Create a review task for the generation run."""

        task = ReviewTask(
            id=str(uuid.uuid4()),
            run_id=run.id,
            run_type=PipelineType.GENERATION,
            required_attestations=1,
            assignees=config.workflow.reviewers,
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

    async def get_generation_run(self, run_id: str) -> GenerationRun:
        """Get a generation run by ID."""
        # TODO: Implement database lookup
        raise NotImplementedError("Database integration required")

    async def list_generations_for_deal(
        self,
        deal_id: str,
        pipeline_id: Optional[str] = None
    ) -> list[GenerationRun]:
        """List all generation runs for a deal."""
        # TODO: Implement database lookup
        raise NotImplementedError("Database integration required")

    async def download_document(
        self,
        run_id: str,
        format: Optional[str] = None
    ) -> bytes:
        """
        Get the generated document for download.

        Args:
            run_id: The generation run ID
            format: Optional format override (markdown, docx)

        Returns:
            Document content as bytes
        """
        run = await self.get_generation_run(run_id)

        if format:
            return self.document_assembler.get_document_bytes(run, format)
        elif run.output_path:
            # Read from file
            with open(run.output_path, "rb") as f:
                return f.read()
        else:
            # Return markdown
            return self.document_assembler.get_document_bytes(run, "markdown")
