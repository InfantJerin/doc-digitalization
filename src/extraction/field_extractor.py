"""
Field Extractor.

Extracts structured fields from documents using Claude API.
Supports batch extraction for efficiency and citation generation.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

try:
    import fitz
except ImportError:
    fitz = None

from ..core.models import (
    DocumentStructure,
    DocumentNode,
    ExtractedField,
    Citation,
    BoundingBox,
)
from ..core.config_loader import ExtractionPipelineConfig, FieldSchemaConfig
from ..core.exceptions import FieldExtractionError
from ..integrations.llm_base import LLMClientProtocol
from ..integrations.llm_factory import get_llm_client

logger = logging.getLogger(__name__)


@dataclass
class ExtractionContext:
    """Context for field extraction."""
    document_path: str
    document_structure: Optional[DocumentStructure]
    page_texts: list[str]
    total_pages: int


class FieldExtractor:
    """
    Extracts fields from documents based on schema configuration.
    Uses batch extraction for efficiency.
    """

    def __init__(self, claude_client: Optional[LLMClientProtocol] = None):
        self.claude_client = claude_client or get_llm_client()

    async def extract_all_fields(
        self,
        pdf_path: str,
        config: ExtractionPipelineConfig,
        structure: Optional[DocumentStructure] = None
    ) -> list[ExtractedField]:
        """
        Extract all fields defined in the pipeline configuration.

        Uses batch extraction - sends relevant sections once and
        extracts all fields in a single LLM call.
        """
        if fitz is None:
            raise FieldExtractionError("all", "PyMuPDF required")

        doc = fitz.open(pdf_path)

        # Build context
        page_texts = [doc[i].get_text() for i in range(len(doc))]
        context = ExtractionContext(
            document_path=pdf_path,
            document_structure=structure,
            page_texts=page_texts,
            total_pages=len(doc)
        )

        # Group fields by their likely sections for efficient batching
        field_batches = self._group_fields_by_sections(config)

        all_fields = []
        for batch in field_batches:
            batch_fields = await self._extract_batch(batch, context, config)
            all_fields.extend(batch_fields)

        doc.close()
        return all_fields

    def _group_fields_by_sections(
        self,
        config: ExtractionPipelineConfig
    ) -> list[dict]:
        """
        Group fields by their likely sections to minimize LLM calls.
        Fields that share sections are batched together.
        """
        # Simple grouping - could be more sophisticated
        batches = []
        current_batch = {
            "fields": [],
            "sections": set(),
        }

        for field_name, field_config in config.extraction_schema.items():
            likely_sections = field_config.likely_sections or []

            # Add to current batch
            current_batch["fields"].append((field_name, field_config))
            current_batch["sections"].update(likely_sections)

            # Start new batch if too many fields (to keep prompt size manageable)
            if len(current_batch["fields"]) >= 10:
                batches.append(current_batch)
                current_batch = {"fields": [], "sections": set()}

        if current_batch["fields"]:
            batches.append(current_batch)

        return batches

    async def _extract_batch(
        self,
        batch: dict,
        context: ExtractionContext,
        config: ExtractionPipelineConfig
    ) -> list[ExtractedField]:
        """Extract a batch of fields from relevant sections."""

        # Get content from relevant sections
        content = self._get_section_content(
            batch["sections"],
            context,
            include_definitions=True
        )

        # Build schema for this batch
        schema = {
            name: {
                "type": fc.type,
                "description": fc.description or name,
                "properties": fc.properties,
            }
            for name, fc in batch["fields"]
        }

        # Build extraction prompt
        prompt = self._build_extraction_prompt(schema, content)

        # Call Claude for batch extraction
        result = await self.claude_client.query_json(
            prompt=prompt,
            max_tokens=4096
        )

        # Parse results into ExtractedField objects
        extracted_fields = []
        for field_name, field_config in batch["fields"]:
            field_result = result.get("extracted_fields", {}).get(field_name, {})

            citation = None
            if "citation" in field_result:
                cite_data = field_result["citation"]
                citation = Citation(
                    field_path=field_name,
                    document_id=context.document_path,
                    page_number=cite_data.get("page", 0),
                    extracted_text=cite_data.get("quote", ""),
                    confidence=field_result.get("confidence", 0.0)
                )

            extracted_field = ExtractedField(
                field_path=field_name,
                value=field_result.get("value"),
                confidence=field_result.get("confidence", 0.0),
                citation=citation
            )
            extracted_fields.append(extracted_field)

        return extracted_fields

    def _get_section_content(
        self,
        section_titles: set[str],
        context: ExtractionContext,
        include_definitions: bool = True
    ) -> str:
        """Get content from specific sections."""

        if not context.document_structure:
            # No structure - return first N pages
            return "\n\n".join(
                f"--- PAGE {i+1} ---\n{text[:3000]}"
                for i, text in enumerate(context.page_texts[:20])
            )

        content_parts = []
        sections_to_fetch = list(section_titles)

        # Always include Definitions for legal docs
        if include_definitions:
            sections_to_fetch = ["Definitions"] + sections_to_fetch

        for section_name in sections_to_fetch:
            node = context.document_structure.get_node_by_title(section_name)
            if node:
                section_text = self._extract_node_content(node, context.page_texts)
                content_parts.append(
                    f"\n\n=== {node.title} (Pages {node.start_page}-{node.end_page}) ===\n\n"
                    f"{section_text}"
                )

        if not content_parts:
            # Fallback to first N pages
            return "\n\n".join(
                f"--- PAGE {i+1} ---\n{text[:3000]}"
                for i, text in enumerate(context.page_texts[:20])
            )

        return "".join(content_parts)

    def _extract_node_content(
        self,
        node: DocumentNode,
        page_texts: list[str]
    ) -> str:
        """Extract text content for a document node."""
        content = ""
        start_idx = max(0, node.start_page - 1)
        end_idx = min(len(page_texts), node.end_page or node.start_page)

        for i in range(start_idx, end_idx):
            content += f"\n--- Page {i + 1} ---\n"
            content += page_texts[i]

        return content

    def _build_extraction_prompt(
        self,
        schema: dict,
        content: str
    ) -> str:
        """Build the extraction prompt for Claude."""

        schema_description = json.dumps(schema, indent=2)

        return f"""You are extracting structured data from a document.

## Document Content
{content}

## Extraction Schema
Extract these fields:
{schema_description}

## Instructions
1. Extract ALL fields defined in the schema from the document
2. For EACH extracted value, provide:
   - The value (matching the expected type)
   - Confidence score (0.0 - 1.0)
   - Citation: page number and exact quote from document
3. If a field cannot be found, set value to null with confidence 0
4. For nested objects, extract all properties

## Output Format
Return valid JSON:
{{
  "extracted_fields": {{
    "<field_name>": {{
      "value": <extracted_value>,
      "confidence": <float 0.0-1.0>,
      "citation": {{
        "page": <int>,
        "quote": "<exact text from document>"
      }}
    }},
    ...
  }},
  "extraction_notes": "<any ambiguities or issues encountered>"
}}

Extract all fields now:"""

    async def extract_single_field(
        self,
        field_name: str,
        field_config: FieldSchemaConfig,
        content: str
    ) -> ExtractedField:
        """
        Extract a single field from document content.
        Useful for re-extraction or validation.
        """
        schema = {
            field_name: {
                "type": field_config.type,
                "description": field_config.description or field_name,
                "properties": field_config.properties,
            }
        }

        prompt = self._build_extraction_prompt(schema, content)
        result = await self.claude_client.query_json(prompt=prompt, max_tokens=1024)

        field_result = result.get("extracted_fields", {}).get(field_name, {})

        citation = None
        if "citation" in field_result:
            cite_data = field_result["citation"]
            citation = Citation(
                field_path=field_name,
                document_id="",
                page_number=cite_data.get("page", 0),
                extracted_text=cite_data.get("quote", ""),
                confidence=field_result.get("confidence", 0.0)
            )

        return ExtractedField(
            field_path=field_name,
            value=field_result.get("value"),
            confidence=field_result.get("confidence", 0.0),
            citation=citation
        )
