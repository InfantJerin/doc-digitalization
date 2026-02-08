"""
Core domain models for the Document Digitalization Platform.

This module contains all the core data models used across the extraction
and generation pipelines.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import uuid


# =============================================================================
# Enums
# =============================================================================

class DealStatus(Enum):
    """Status of a deal in the system."""
    PENDING_DOCS = "pending_docs"
    READY = "ready"
    PROCESSING = "processing"
    COMPLETED = "completed"


class DocumentSourceChannel(Enum):
    """Channel through which a document was received."""
    S3 = "s3"
    API = "api"
    EMAIL = "email"
    FOLDER_WATCH = "folder_watch"


class PipelineType(Enum):
    """Type of pipeline."""
    EXTRACTION = "extraction"
    GENERATION = "generation"


class RunStatus(Enum):
    """Status of a pipeline run."""
    PENDING = "pending"
    PROCESSING = "processing"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"


class ReviewStatus(Enum):
    """Status of a review task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"


class AttestationDecision(Enum):
    """Decision made during attestation."""
    APPROVED = "approved"
    REJECTED = "rejected"
    OVERRIDE = "override"


class ValidationType(Enum):
    """Type of validation for data points."""
    EXACT_MATCH = "exact_match"
    FUZZY_MATCH = "fuzzy_match"
    NUMERIC_EXACT = "numeric_exact"
    NUMERIC_TOLERANCE = "numeric_tolerance"
    LIST_MATCH = "list_match"
    STRUCTURED_MATCH = "structured_match"


class ValidationStatus(Enum):
    """Status of data point validation."""
    VALIDATED = "validated"
    CONFLICT = "conflict"
    SINGLE_SOURCE = "single_source"
    MISSING = "missing"


class ExtractionMode(Enum):
    """Method used to extract document structure."""
    PDF_BOOKMARKS = "pdf_bookmarks"
    TOC_WITH_PAGES = "toc_with_pages"
    TOC_WITHOUT_PAGES = "toc_no_pages"
    HEADING_DETECTION = "heading_detect"
    CONTENT_GENERATION = "content_gen"


# =============================================================================
# Core Domain Models
# =============================================================================

@dataclass
class Deal:
    """
    A deal represents a loan or transaction that groups related documents.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    external_id: str = ""  # Client's loan/deal ID
    status: DealStatus = DealStatus.PENDING_DOCS
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Document:
    """
    A document uploaded to the system, linked to a deal.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    deal_id: str = ""
    document_type: str = ""  # e.g., "compliance_certificate", "financial_statement"
    source_channel: DocumentSourceChannel = DocumentSourceChannel.API
    storage_path: str = ""  # S3 path
    original_filename: str = ""
    content_hash: str = ""
    mime_type: str = ""
    page_count: int = 0
    ocr_required: bool = False
    ocr_completed: bool = False
    received_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)


# =============================================================================
# Document Structure Models (for large document handling)
# =============================================================================

@dataclass
class DocumentNode:
    """
    A node in the document structure tree.
    Used for hierarchical navigation of large documents.
    """
    id: str = ""
    title: str = ""
    level: int = 0  # 0 = root, 1 = Article, 2 = Section, 3 = Subsection
    start_page: int = 1
    end_page: Optional[int] = None
    summary: Optional[str] = None
    children: list["DocumentNode"] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "level": self.level,
            "start_page": self.start_page,
            "end_page": self.end_page,
            "summary": self.summary,
            "children": [c.to_dict() for c in self.children]
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DocumentNode":
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            level=data.get("level", 0),
            start_page=data.get("start_page", 1),
            end_page=data.get("end_page"),
            summary=data.get("summary"),
            children=[cls.from_dict(c) for c in data.get("children", [])]
        )

    @property
    def page_count(self) -> int:
        if self.end_page is None:
            return 1
        return max(1, self.end_page - self.start_page + 1)


@dataclass
class DocumentStructure:
    """
    The complete structure of a document, including the extraction method used.
    """
    document_id: str = ""
    root: DocumentNode = field(default_factory=DocumentNode)
    mode_used: ExtractionMode = ExtractionMode.PDF_BOOKMARKS
    total_pages: int = 0
    toc_pages: list[int] = field(default_factory=list)
    extracted_at: datetime = field(default_factory=datetime.utcnow)

    def get_node_by_title(self, title: str) -> Optional[DocumentNode]:
        """Find node by title (case-insensitive partial match)."""
        return self._search_node(self.root, title.lower())

    def _search_node(self, node: DocumentNode, query: str) -> Optional[DocumentNode]:
        if query in node.title.lower():
            return node
        for child in node.children:
            result = self._search_node(child, query)
            if result:
                return result
        return None

    def get_all_nodes(self) -> list[DocumentNode]:
        """Get all nodes as a flat list."""
        nodes = []
        self._collect_nodes(self.root, nodes)
        return nodes

    def _collect_nodes(self, node: DocumentNode, nodes: list):
        if node.level > 0:
            nodes.append(node)
        for child in node.children:
            self._collect_nodes(child, nodes)


# =============================================================================
# Citation Models
# =============================================================================

@dataclass
class BoundingBox:
    """Bounding box coordinates for highlighting text in a document."""
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0


@dataclass
class Citation:
    """
    A citation linking an extracted value to its source in a document.
    """
    field_path: str = ""  # e.g., "covenant_period.start_date"
    document_id: str = ""
    page_number: int = 0
    bounding_box: Optional[BoundingBox] = None
    extracted_text: str = ""
    confidence: float = 0.0


# =============================================================================
# Extraction Models
# =============================================================================

@dataclass
class ExtractedField:
    """
    A single extracted field with its value, confidence, and citation.
    """
    field_path: str = ""
    value: Any = None
    confidence: float = 0.0
    citation: Optional[Citation] = None
    attested: bool = False
    attested_by: Optional[str] = None
    attested_at: Optional[datetime] = None
    overridden: bool = False
    override_value: Any = None
    override_justification: Optional[str] = None


@dataclass
class ExtractionRun:
    """
    A single execution of an extraction pipeline.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    deal_id: str = ""
    pipeline_id: str = ""
    version: int = 1  # Revision number
    status: RunStatus = RunStatus.PENDING
    document_ids: list[str] = field(default_factory=list)
    extracted_fields: list[ExtractedField] = field(default_factory=list)
    agent_session_id: Optional[str] = None
    triggered_by: str = ""  # "manual:user@example.com" or "rule:doc_arrival"
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def get_field(self, path: str) -> Optional[ExtractedField]:
        """Get an extracted field by its path."""
        for f in self.extracted_fields:
            if f.field_path == path:
                return f
        return None


# =============================================================================
# Review and Attestation Models
# =============================================================================

@dataclass
class FieldOverride:
    """
    An override of an extracted field value.
    """
    field_path: str = ""
    original_value: Any = None
    new_value: Any = None
    justification: str = ""  # Required for audit trail


@dataclass
class Attestation:
    """
    An attestation (approval/rejection/override) by a reviewer.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    reviewer_id: str = ""
    reviewer_email: str = ""
    decision: AttestationDecision = AttestationDecision.APPROVED
    fields_attested: list[str] = field(default_factory=list)
    overrides: list[FieldOverride] = field(default_factory=list)
    comments: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ReviewTask:
    """
    A review task for the maker-checker workflow.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str = ""  # ExtractionRun or GenerationRun ID
    run_type: PipelineType = PipelineType.EXTRACTION
    assignees: list[str] = field(default_factory=list)
    required_attestations: int = 1
    attestations: list[Attestation] = field(default_factory=list)
    status: ReviewStatus = ReviewStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    @property
    def is_fully_attested(self) -> bool:
        approved_count = sum(
            1 for a in self.attestations
            if a.decision in [AttestationDecision.APPROVED, AttestationDecision.OVERRIDE]
        )
        return approved_count >= self.required_attestations


# =============================================================================
# Generation Pipeline Models
# =============================================================================

@dataclass
class DataPointValue:
    """
    A value extracted from a single source for a data point.
    """
    source_id: str = ""
    source_type: str = ""  # "api", "dms", "extraction_pipeline"
    value: Any = None
    confidence: float = 1.0
    citation: Optional[Citation] = None


@dataclass
class DataPointValidation:
    """
    Result of cross-source validation for a data point.
    """
    data_point_id: str = ""
    description: str = ""
    validation_type: ValidationType = ValidationType.EXACT_MATCH
    status: ValidationStatus = ValidationStatus.VALIDATED
    source_values: list[DataPointValue] = field(default_factory=list)
    canonical_value: Any = None
    canonical_source: Optional[str] = None
    conflict_details: Optional[str] = None
    max_deviation: Optional[float] = None  # For numeric tolerance


@dataclass
class SectionDataPoints:
    """
    All data points for a generated section.
    """
    section_id: str = ""
    data_points: list[DataPointValidation] = field(default_factory=list)

    @property
    def has_conflicts(self) -> bool:
        return any(dp.status == ValidationStatus.CONFLICT for dp in self.data_points)

    @property
    def conflict_count(self) -> int:
        return sum(1 for dp in self.data_points if dp.status == ValidationStatus.CONFLICT)


@dataclass
class GeneratedSection:
    """
    A generated section of a document.
    """
    section_id: str = ""
    section_name: str = ""
    content: str = ""  # Markdown content
    data_points: Optional[SectionDataPoints] = None
    citations: list[Citation] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.utcnow)
    regenerated: bool = False
    edited: bool = False
    edited_content: Optional[str] = None


@dataclass
class GenerationRun:
    """
    A single execution of a generation pipeline.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    deal_id: str = ""
    pipeline_id: str = ""
    version: int = 1
    status: RunStatus = RunStatus.PENDING
    sections: list[GeneratedSection] = field(default_factory=list)
    output_path: Optional[str] = None  # S3 path to generated document
    output_format: str = "docx"
    triggered_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    @property
    def has_conflicts(self) -> bool:
        return any(s.data_points and s.data_points.has_conflicts for s in self.sections)


# =============================================================================
# Revision Models
# =============================================================================

@dataclass
class FieldRevision:
    """
    A revision entry for a single field.
    """
    field_path: str = ""
    version: int = 1
    value: Any = None
    source: str = ""  # "ai_extracted" or "manual_override"
    changed_by: Optional[str] = None
    changed_at: datetime = field(default_factory=datetime.utcnow)
    justification: Optional[str] = None


@dataclass
class RevisionHistory:
    """
    Complete revision history for a run.
    """
    run_id: str = ""
    run_type: PipelineType = PipelineType.EXTRACTION
    revisions: list[FieldRevision] = field(default_factory=list)

    def get_field_history(self, field_path: str) -> list[FieldRevision]:
        return [r for r in self.revisions if r.field_path == field_path]


# =============================================================================
# Webhook / Post-Sink Models
# =============================================================================

@dataclass
class WebhookDelivery:
    """
    Record of a webhook delivery attempt.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str = ""
    webhook_url: str = ""
    payload: dict = field(default_factory=dict)
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    success: bool = False
    attempt_number: int = 1
    attempted_at: datetime = field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None
