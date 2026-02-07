"""
Extraction pipeline module.

This module handles extracting structured data from documents,
including large document handling via hierarchical structure detection.
"""

from .service import ExtractionService
from .structure_extractor import DocumentStructureExtractor
from .field_extractor import FieldExtractor
from .citation_builder import CitationBuilder

__all__ = [
    "ExtractionService",
    "DocumentStructureExtractor",
    "FieldExtractor",
    "CitationBuilder",
]
