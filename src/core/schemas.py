"""Pydantic schemas for API and agent structured output."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class CitationOutput(BaseModel):
    """Structured citation emitted by the extraction agent."""

    document_id: Optional[str] = None
    page_number: int = 0
    extracted_text: str = ""
    confidence: float = 0.0
    bounding_box: Optional[dict[str, float]] = None


class ExtractedFieldOutput(BaseModel):
    """Structured field emitted by the extraction agent."""

    field_path: str
    value: Any = None
    confidence: float = 0.0
    citation: Optional[CitationOutput] = None
    notes: Optional[str] = None


class ExtractionResultOutput(BaseModel):
    """Top-level extraction result payload from the agent."""

    fields: list[ExtractedFieldOutput] = Field(default_factory=list)
    extraction_notes: list[str] = Field(default_factory=list)
    agent_session_id: Optional[str] = None


class ExtractionCreateRequest(BaseModel):
    """API request for creating extraction runs."""

    deal_id: str
    pipeline_id: str
    document_ids: list[str]
    triggered_by: str


class ExtractionCreateResponse(BaseModel):
    """API response after extraction run is created/executed."""

    run_id: str
    status: str
    message: str


class HealthStatus(BaseModel):
    """Health/readiness response."""

    status: str
    timestamp: datetime
    checks: dict[str, str] = Field(default_factory=dict)
