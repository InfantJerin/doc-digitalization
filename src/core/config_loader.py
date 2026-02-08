"""
Configuration loader for pipeline YAML files.

This module handles loading and validating pipeline configurations
from YAML files in the config/pipelines directory.
"""

import os
import re
from pathlib import Path
from typing import Optional
import yaml
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, field_validator
from enum import Enum


# =============================================================================
# Configuration Models (Pydantic for validation)
# =============================================================================

class TriggerType(str, Enum):
    MANUAL = "manual"
    DOCUMENT_SET_COMPLETE = "document_set_complete"
    EXTERNAL_EVENT = "external_event"
    SCHEDULE = "schedule"


class ValidationTypeConfig(str, Enum):
    EXACT_MATCH = "exact_match"
    FUZZY_MATCH = "fuzzy_match"
    NUMERIC_EXACT = "numeric_exact"
    NUMERIC_TOLERANCE = "numeric_tolerance"
    LIST_MATCH = "list_match"
    STRUCTURED_MATCH = "structured_match"


class DataSourceType(str, Enum):
    API = "api"
    DMS = "dms"
    EXTRACTION_PIPELINE = "extraction_pipeline"
    DATABASE = "database"


# =============================================================================
# Extraction Pipeline Configuration
# =============================================================================

class DocumentRequirementConfig(BaseModel):
    """Configuration for a required document type."""
    type: str
    required: bool = True
    multi: bool = False  # Can have multiple documents of this type
    aliases: list[str] = Field(default_factory=list)


class TriggerRuleConfig(BaseModel):
    """Configuration for an automatic trigger rule."""
    name: str
    when: dict
    action: str = "trigger_extraction"
    document_selection: str = "latest_of_each_type"


class ManualTriggerConfig(BaseModel):
    """Configuration for manual triggering."""
    enabled: bool = True
    roles: list[str] = Field(default_factory=lambda: ["loan_ops"])


class ApiTriggerConfig(BaseModel):
    """Configuration for API triggering."""
    enabled: bool = True


class TriggersConfig(BaseModel):
    """Configuration for all trigger types."""
    manual: ManualTriggerConfig = Field(default_factory=ManualTriggerConfig)
    rules: list[TriggerRuleConfig] = Field(default_factory=list)
    api: ApiTriggerConfig = Field(default_factory=ApiTriggerConfig)

    @field_validator("api", mode="before")
    @classmethod
    def normalize_api(cls, value):
        if isinstance(value, bool):
            return {"enabled": value}
        if isinstance(value, dict):
            return value
        return {"enabled": True}


class FieldSchemaConfig(BaseModel):
    """Configuration for a field in the extraction schema."""
    type: str
    description: Optional[str] = None
    properties: Optional[dict] = None
    items: Optional[dict] = None
    likely_sections: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    required: bool = True
    cross_validate: bool = False
    skill: Optional[str] = None


class LargeDocumentConfig(BaseModel):
    """Configuration for handling large documents."""
    enabled: bool = False
    strategy: str = "section_based"  # "section_based", "rag", "hybrid"
    max_pages_per_batch: int = 100
    always_include_sections: list[str] = Field(default_factory=lambda: ["Definitions"])


class MultiAttestConfig(BaseModel):
    """Configuration for multi-attestation."""
    required_count: int = 1
    roles: list[str] = Field(default_factory=list)


class MakerCheckerConfig(BaseModel):
    """Configuration for maker-checker workflow."""
    enabled: bool = True
    auto_approve_threshold: float = 0.95
    multi_attest: MultiAttestConfig = Field(default_factory=MultiAttestConfig)


class OverridePolicyConfig(BaseModel):
    """Configuration for override policies."""
    require_justification: bool = True
    min_justification_length: int = 20


class WorkflowConfig(BaseModel):
    """Configuration for the review workflow."""
    maker_checker: MakerCheckerConfig = Field(default_factory=MakerCheckerConfig)
    override_policy: OverridePolicyConfig = Field(default_factory=OverridePolicyConfig)


class PostSinkConfig(BaseModel):
    """Configuration for a post-processing sink."""
    type: str  # "webhook", "api", "database"
    url: Optional[str] = None
    endpoint: Optional[str] = None
    auth: Optional[str] = None
    connection: Optional[str] = None
    table: Optional[str] = None
    headers: dict = Field(default_factory=dict)


class ExtractionPipelineConfig(BaseModel):
    """Complete configuration for an extraction pipeline."""
    id: str
    name: str
    description: Optional[str] = None

    document_types: list[DocumentRequirementConfig]
    large_document_handling: LargeDocumentConfig = Field(
        default_factory=LargeDocumentConfig
    )

    triggers: TriggersConfig = Field(default_factory=TriggersConfig)
    extraction_schema: dict[str, FieldSchemaConfig]
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    post_sinks: list[PostSinkConfig] = Field(default_factory=list)

    class Config:
        extra = "allow"


# =============================================================================
# Generation Pipeline Configuration
# =============================================================================

class OutputConfig(BaseModel):
    """Configuration for generation output."""
    format: str = "docx"  # docx, pdf, markdown
    filename_template: str = "{pipeline_id}_{deal_id}_{date}.{format}"
    store_in_dms: bool = True


class DataSourceConfig(BaseModel):
    """Configuration for a data source."""
    type: DataSourceType
    endpoint: Optional[str] = None
    auth: Optional[str] = None
    document_types: list[str] = Field(default_factory=list)
    extraction_schema: Optional[str] = None
    pipeline_id: Optional[str] = None
    connection: Optional[str] = None
    query: Optional[str] = None


class DataPointConfig(BaseModel):
    """Configuration for a data point in a section."""
    id: str
    description: str
    sources: list[str]
    validation: ValidationTypeConfig = ValidationTypeConfig.EXACT_MATCH
    tolerance: float = 0.05  # For numeric tolerance
    required: bool = True
    unit: Optional[str] = None


class SectionConfig(BaseModel):
    """Configuration for a document section."""
    id: str
    name: str
    instructions: str
    data_sources: list[str] = Field(default_factory=list)
    data_points: list[DataPointConfig] = Field(default_factory=list)
    max_words: Optional[int] = None
    include_tables: bool = False
    subsections: list["SectionConfig"] = Field(default_factory=list)


# Forward reference resolution
SectionConfig.update_forward_refs()


class StyleConfig(BaseModel):
    """Configuration for document style."""
    tone: str = "formal"
    perspective: str = "third_person"


class TemplateConfig(BaseModel):
    """Configuration for the document template."""
    style: StyleConfig = Field(default_factory=StyleConfig)
    sections: list[SectionConfig]


class GenerationWorkflowConfig(BaseModel):
    """Configuration for generation workflow."""
    review_required: bool = True
    reviewers: list[str] = Field(default_factory=list)
    allow_section_regeneration: bool = True
    allow_inline_editing: bool = True


class GenerationPipelineConfig(BaseModel):
    """Complete configuration for a generation pipeline."""
    id: str
    name: str
    description: Optional[str] = None

    output: OutputConfig = Field(default_factory=OutputConfig)
    data_sources: dict[str, DataSourceConfig]
    template: TemplateConfig
    workflow: GenerationWorkflowConfig = Field(default_factory=GenerationWorkflowConfig)

    class Config:
        extra = "allow"


# =============================================================================
# Configuration Loader
# =============================================================================

class ConfigLoader:
    """
    Loads and manages pipeline configurations from YAML files.
    """

    def __init__(self, config_dir: Optional[str] = None):
        if config_dir is None:
            # Default to config/pipelines relative to project root
            self.config_dir = Path(__file__).parent.parent.parent / "config" / "pipelines"
        else:
            self.config_dir = Path(config_dir)

        self._extraction_cache: dict[str, ExtractionPipelineConfig] = {}
        self._generation_cache: dict[str, GenerationPipelineConfig] = {}

    def load_extraction_pipeline(self, pipeline_id: str) -> ExtractionPipelineConfig:
        """Load an extraction pipeline configuration by ID."""
        if pipeline_id in self._extraction_cache:
            return self._extraction_cache[pipeline_id]

        config_path = self.config_dir / "extraction" / f"{pipeline_id}.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"Extraction pipeline config not found: {config_path}")

        with open(config_path) as f:
            raw_config = yaml.safe_load(f)

        # Handle nested structure (extraction_use_case key)
        if "extraction_use_case" in raw_config:
            raw_config = raw_config["extraction_use_case"]

        config = ExtractionPipelineConfig(**raw_config)
        self._extraction_cache[pipeline_id] = config
        return config

    def load_generation_pipeline(self, pipeline_id: str) -> GenerationPipelineConfig:
        """Load a generation pipeline configuration by ID."""
        if pipeline_id in self._generation_cache:
            return self._generation_cache[pipeline_id]

        config_path = self.config_dir / "generation" / f"{pipeline_id}.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"Generation pipeline config not found: {config_path}")

        with open(config_path) as f:
            raw_config = yaml.safe_load(f)

        # Handle nested structure (generation_pipeline key)
        if "generation_pipeline" in raw_config:
            raw_config = raw_config["generation_pipeline"]

        config = GenerationPipelineConfig(**raw_config)
        self._generation_cache[pipeline_id] = config
        return config

    def list_extraction_pipelines(self) -> list[str]:
        """List all available extraction pipeline IDs."""
        extraction_dir = self.config_dir / "extraction"
        if not extraction_dir.exists():
            return []
        return [f.stem for f in extraction_dir.glob("*.yaml")]

    def list_generation_pipelines(self) -> list[str]:
        """List all available generation pipeline IDs."""
        generation_dir = self.config_dir / "generation"
        if not generation_dir.exists():
            return []
        return [f.stem for f in generation_dir.glob("*.yaml")]

    def reload(self):
        """Clear caches and force reload on next access."""
        self._extraction_cache.clear()
        self._generation_cache.clear()

    def resolve_field_skill_name(
        self,
        field_name: str,
        field_config: Optional[FieldSchemaConfig] = None,
    ) -> str:
        """
        Resolve the canonical skill name for a field.

        Fields can override via `skill` in YAML. Otherwise we use the
        field path converted to hyphen-case.
        """
        if field_config and field_config.skill:
            return field_config.skill.strip()

        normalized = re.sub(r"[^a-zA-Z0-9]+", "-", field_name).strip("-")
        return normalized.lower()

    def list_extraction_skill_names(self, pipeline_id: str) -> dict[str, str]:
        """Return map of field path -> resolved skill name for a pipeline."""
        config = self.load_extraction_pipeline(pipeline_id)
        return {
            field_name: self.resolve_field_skill_name(field_name, field_config)
            for field_name, field_config in config.extraction_schema.items()
        }


# Global config loader instance
_config_loader: Optional[ConfigLoader] = None


def get_config_loader() -> ConfigLoader:
    """Get the global config loader instance."""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader


def load_extraction_config(pipeline_id: str) -> ExtractionPipelineConfig:
    """Convenience function to load an extraction pipeline config."""
    return get_config_loader().load_extraction_pipeline(pipeline_id)


def load_generation_config(pipeline_id: str) -> GenerationPipelineConfig:
    """Convenience function to load a generation pipeline config."""
    return get_config_loader().load_generation_pipeline(pipeline_id)
