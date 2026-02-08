"""
Custom exceptions for the Document Digitalization Platform.
"""


class DocDigitalizationError(Exception):
    """Base exception for all platform errors."""
    pass


# =============================================================================
# Configuration Errors
# =============================================================================

class ConfigurationError(DocDigitalizationError):
    """Error in pipeline configuration."""
    pass


class PipelineNotFoundError(ConfigurationError):
    """Pipeline configuration not found."""
    def __init__(self, pipeline_id: str, pipeline_type: str = "extraction"):
        self.pipeline_id = pipeline_id
        self.pipeline_type = pipeline_type
        super().__init__(f"{pipeline_type.capitalize()} pipeline not found: {pipeline_id}")


class InvalidConfigurationError(ConfigurationError):
    """Invalid pipeline configuration."""
    pass


# =============================================================================
# Document Errors
# =============================================================================

class DocumentError(DocDigitalizationError):
    """Error related to document processing."""
    pass


class DocumentNotFoundError(DocumentError):
    """Document not found in storage."""
    def __init__(self, document_id: str):
        self.document_id = document_id
        super().__init__(f"Document not found: {document_id}")


class DocumentProcessingError(DocumentError):
    """Error processing a document."""
    pass


class UnsupportedDocumentTypeError(DocumentError):
    """Document type is not supported."""
    def __init__(self, mime_type: str):
        self.mime_type = mime_type
        super().__init__(f"Unsupported document type: {mime_type}")


class OCRError(DocumentError):
    """Error during OCR processing."""
    pass


# =============================================================================
# Extraction Errors
# =============================================================================

class ExtractionError(DocDigitalizationError):
    """Error during extraction pipeline execution."""
    pass


class StructureExtractionError(ExtractionError):
    """Error extracting document structure."""
    pass


class FieldExtractionError(ExtractionError):
    """Error extracting a specific field."""
    def __init__(self, field_path: str, reason: str):
        self.field_path = field_path
        self.reason = reason
        super().__init__(f"Failed to extract field '{field_path}': {reason}")


class LowConfidenceError(ExtractionError):
    """Extraction confidence below threshold."""
    def __init__(self, field_path: str, confidence: float, threshold: float):
        self.field_path = field_path
        self.confidence = confidence
        self.threshold = threshold
        super().__init__(
            f"Low confidence for field '{field_path}': {confidence:.2f} < {threshold:.2f}"
        )


class AgentError(ExtractionError):
    """Error raised by the Agent SDK orchestration layer."""
    pass


class AgentBudgetExceededError(AgentError):
    """Agent exceeded configured turn or cost budgets."""
    def __init__(self, pipeline_id: str, reason: str):
        self.pipeline_id = pipeline_id
        self.reason = reason
        super().__init__(f"Agent budget exceeded for '{pipeline_id}': {reason}")


# =============================================================================
# Generation Errors
# =============================================================================

class GenerationError(DocDigitalizationError):
    """Error during generation pipeline execution."""
    pass


class DataGatheringError(GenerationError):
    """Error gathering data from sources."""
    def __init__(self, source_id: str, reason: str):
        self.source_id = source_id
        self.reason = reason
        super().__init__(f"Failed to gather data from '{source_id}': {reason}")


class DataPointConflictError(GenerationError):
    """Conflict detected in data point validation."""
    def __init__(self, data_point_id: str, values: list):
        self.data_point_id = data_point_id
        self.values = values
        super().__init__(
            f"Conflict in data point '{data_point_id}': {values}"
        )


class SectionGenerationError(GenerationError):
    """Error generating a document section."""
    def __init__(self, section_id: str, reason: str):
        self.section_id = section_id
        self.reason = reason
        super().__init__(f"Failed to generate section '{section_id}': {reason}")


class DocumentAssemblyError(GenerationError):
    """Error assembling the final document."""
    pass


# =============================================================================
# Workflow Errors
# =============================================================================

class WorkflowError(DocDigitalizationError):
    """Error in the review workflow."""
    pass


class ReviewTaskNotFoundError(WorkflowError):
    """Review task not found."""
    def __init__(self, task_id: str):
        self.task_id = task_id
        super().__init__(f"Review task not found: {task_id}")


class AttestationError(WorkflowError):
    """Error during attestation."""
    pass


class InvalidOverrideError(WorkflowError):
    """Invalid override attempt."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Invalid override: {reason}")


class JustificationRequiredError(WorkflowError):
    """Justification required for override."""
    def __init__(self, field_path: str):
        self.field_path = field_path
        super().__init__(f"Justification required for override of field '{field_path}'")


# =============================================================================
# Integration Errors
# =============================================================================

class IntegrationError(DocDigitalizationError):
    """Error with external service integration."""
    pass


class DMSError(IntegrationError):
    """Error communicating with Document Management System."""
    pass


class LLMError(IntegrationError):
    """Error communicating with LLM (Claude)."""
    pass


class WebhookError(IntegrationError):
    """Error delivering webhook."""
    def __init__(self, url: str, status_code: int, reason: str):
        self.url = url
        self.status_code = status_code
        self.reason = reason
        super().__init__(f"Webhook delivery failed to {url}: {status_code} - {reason}")


# =============================================================================
# Deal Errors
# =============================================================================

class DealError(DocDigitalizationError):
    """Error related to deals."""
    pass


class DealNotFoundError(DealError):
    """Deal not found."""
    def __init__(self, deal_id: str):
        self.deal_id = deal_id
        super().__init__(f"Deal not found: {deal_id}")


class DocumentsNotReadyError(DealError):
    """Required documents not yet available for deal."""
    def __init__(self, deal_id: str, missing_types: list[str]):
        self.deal_id = deal_id
        self.missing_types = missing_types
        super().__init__(
            f"Missing documents for deal {deal_id}: {', '.join(missing_types)}"
        )
