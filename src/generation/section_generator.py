"""
Section Generator.

Generates document sections using LLM, with validated data points
and source citations.
"""

import logging
from datetime import datetime
from typing import Optional
import json

from ..core.models import (
    GeneratedSection,
    SectionDataPoints,
    DataPointValidation,
    ValidationStatus,
    Citation,
)
from ..core.config_loader import SectionConfig, DataPointConfig
from ..integrations.claude_client import ClaudeClient
from .data_point_validator import DataContext, DataPointValidator

logger = logging.getLogger(__name__)


class SectionGenerator:
    """
    Generates document sections with validated data points.

    The generation process:
    1. Validate data points across sources
    2. Build prompt with validated values
    3. Generate section content
    4. Track citations for each data point used
    """

    def __init__(
        self,
        claude_client: Optional[ClaudeClient] = None,
        data_point_validator: Optional[DataPointValidator] = None
    ):
        self.claude_client = claude_client or ClaudeClient()
        self.data_point_validator = data_point_validator or DataPointValidator()

    async def generate_section(
        self,
        section_config: SectionConfig,
        data_context: DataContext,
        style_config: Optional[dict] = None
    ) -> GeneratedSection:
        """
        Generate a single document section.

        Args:
            section_config: Configuration for the section
            data_context: Data from all sources
            style_config: Style configuration (tone, perspective)

        Returns:
            GeneratedSection with content, data points, and citations
        """
        logger.info(f"Generating section: {section_config.name}")

        # Step 1: Validate data points for this section
        data_points = None
        if section_config.data_points:
            data_points = await self.data_point_validator.validate_section_data_points(
                section_id=section_config.id,
                data_point_configs=section_config.data_points,
                data_context=data_context
            )

            if data_points.has_conflicts:
                logger.warning(
                    f"Section {section_config.id} has {data_points.conflict_count} "
                    f"data point conflicts"
                )

        # Step 2: Build generation prompt
        prompt = self._build_section_prompt(
            section_config,
            data_context,
            data_points,
            style_config
        )

        # Step 3: Generate content
        result = await self.claude_client.query_json(
            prompt=prompt,
            max_tokens=2048
        )

        content = result.get("content", "")
        citations_data = result.get("citations", [])

        # Step 4: Build citations
        citations = [
            Citation(
                field_path=c.get("data_point", ""),
                document_id=c.get("source", ""),
                page_number=c.get("page", 0),
                extracted_text=c.get("quote", ""),
                confidence=1.0
            )
            for c in citations_data
        ]

        return GeneratedSection(
            section_id=section_config.id,
            section_name=section_config.name,
            content=content,
            data_points=data_points,
            citations=citations,
            generated_at=datetime.utcnow()
        )

    def _build_section_prompt(
        self,
        section_config: SectionConfig,
        data_context: DataContext,
        data_points: Optional[SectionDataPoints],
        style_config: Optional[dict]
    ) -> str:
        """Build the generation prompt for a section."""

        # Style instructions
        style_str = ""
        if style_config:
            tone = style_config.get("tone", "formal")
            perspective = style_config.get("perspective", "third_person")
            style_str = f"""
## Style
- Tone: {tone}
- Perspective: {perspective}
"""

        # Data points section
        data_points_str = ""
        if data_points and data_points.data_points:
            data_points_str = "\n## Data Points (Use These Exact Values)\n"
            for dp in data_points.data_points:
                status_marker = {
                    ValidationStatus.VALIDATED: "VALIDATED",
                    ValidationStatus.CONFLICT: "CONFLICT - needs review",
                    ValidationStatus.SINGLE_SOURCE: "SINGLE SOURCE",
                    ValidationStatus.MISSING: "MISSING"
                }[dp.status]

                if dp.canonical_value is not None:
                    data_points_str += f"- {dp.description}: {dp.canonical_value} [{status_marker}]\n"
                    if dp.status == ValidationStatus.CONFLICT:
                        data_points_str += f"  Conflicting values: {dp.conflict_details}\n"
                else:
                    data_points_str += f"- {dp.description}: NOT AVAILABLE [{status_marker}]\n"

        # Source context
        source_context = self._format_source_context(
            data_context,
            section_config.data_sources
        )

        # Word limit
        word_limit = ""
        if section_config.max_words:
            word_limit = f"\n- Maximum {section_config.max_words} words"

        # Build final prompt
        prompt = f"""## Task
Generate the "{section_config.name}" section of a document.

## Instructions
{section_config.instructions}
{style_str}
{data_points_str}
## Source Context
{source_context}

## Output Requirements
- Use the validated data points exactly as provided
- For conflicting data points, use the most reliable source value
- Write clear, professional content
- Include citations for key facts{word_limit}
- Format as markdown

## Output Format
Return JSON:
{{
  "content": "<section content in markdown>",
  "citations": [
    {{
      "data_point": "<data point id>",
      "source": "<source id>",
      "page": <page number if from document>,
      "quote": "<exact quote if from document>"
    }}
  ]
}}

Generate the section now:"""

        return prompt

    def _format_source_context(
        self,
        data_context: DataContext,
        source_ids: list[str]
    ) -> str:
        """Format source data for the prompt."""
        context_parts = []

        for source_id in source_ids:
            source_data = data_context.sources.get(source_id)
            if source_data:
                # Limit data size in prompt
                data_str = json.dumps(source_data, indent=2, default=str)
                if len(data_str) > 3000:
                    data_str = data_str[:3000] + "\n... (truncated)"

                context_parts.append(f"### Source: {source_id}\n{data_str}")

        return "\n\n".join(context_parts) if context_parts else "No source data available."

    async def regenerate_section(
        self,
        section: GeneratedSection,
        section_config: SectionConfig,
        data_context: DataContext,
        user_feedback: Optional[str] = None,
        style_config: Optional[dict] = None
    ) -> GeneratedSection:
        """
        Regenerate a section with optional user feedback.

        Used when a reviewer requests regeneration with specific changes.
        """
        logger.info(f"Regenerating section: {section_config.name}")

        # Add user feedback to instructions
        instructions = section_config.instructions
        if user_feedback:
            instructions = f"{instructions}\n\nUser feedback: {user_feedback}"

        # Create modified config
        modified_config = SectionConfig(
            id=section_config.id,
            name=section_config.name,
            instructions=instructions,
            data_sources=section_config.data_sources,
            data_points=section_config.data_points,
            max_words=section_config.max_words,
            include_tables=section_config.include_tables
        )

        # Generate new section
        new_section = await self.generate_section(
            modified_config,
            data_context,
            style_config
        )

        new_section.regenerated = True
        return new_section
