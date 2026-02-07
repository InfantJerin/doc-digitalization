"""
Data Point Validator.

Validates data points across multiple sources, detecting conflicts
and determining canonical values.
"""

import logging
from dataclasses import dataclass
from typing import Any, Optional
from difflib import SequenceMatcher

from ..core.models import (
    DataPointValue,
    DataPointValidation,
    SectionDataPoints,
    ValidationStatus,
    ValidationType,
    Citation,
)
from ..core.config_loader import DataPointConfig

logger = logging.getLogger(__name__)


@dataclass
class DataContext:
    """Context containing data from all sources."""
    sources: dict[str, Any]  # source_id -> data
    citations: dict[str, list[Citation]]  # source_id -> citations


class DataPointValidator:
    """
    Validates data points across multiple sources.

    Handles different validation types:
    - exact_match: Values must be identical
    - fuzzy_match: Allow minor text variations
    - numeric_exact: Numbers must match exactly
    - numeric_tolerance: Numbers within percentage tolerance
    - list_match: Lists contain same items
    - structured_match: Complex object comparison
    """

    def __init__(self, default_tolerance: float = 0.05):
        self.default_tolerance = default_tolerance

    async def validate_section_data_points(
        self,
        section_id: str,
        data_point_configs: list[DataPointConfig],
        data_context: DataContext
    ) -> SectionDataPoints:
        """
        Validate all data points for a section.

        Returns validated data points with status and canonical values.
        """
        validations = []

        for dp_config in data_point_configs:
            # Extract value from each configured source
            source_values = []
            for source_id in dp_config.sources:
                value = self._extract_data_point_from_source(
                    dp_config,
                    source_id,
                    data_context
                )
                if value is not None:
                    source_values.append(value)

            # Cross-validate across sources
            validation = self._cross_validate(dp_config, source_values)
            validations.append(validation)

        return SectionDataPoints(
            section_id=section_id,
            data_points=validations
        )

    def _extract_data_point_from_source(
        self,
        dp_config: DataPointConfig,
        source_id: str,
        data_context: DataContext
    ) -> Optional[DataPointValue]:
        """Extract a data point value from a specific source."""
        source_data = data_context.sources.get(source_id)
        if source_data is None:
            return None

        # Try to find the value in the source data
        value = self._find_value_in_data(dp_config.id, source_data)
        if value is None:
            return None

        # Get citation if available
        citations = data_context.citations.get(source_id, [])
        citation = next(
            (c for c in citations if c.field_path == dp_config.id),
            None
        )

        return DataPointValue(
            source_id=source_id,
            source_type=self._get_source_type(source_id, data_context),
            value=value,
            confidence=1.0 if citation else 0.8,
            citation=citation
        )

    def _find_value_in_data(self, key: str, data: Any) -> Any:
        """Find a value in nested data structure."""
        if isinstance(data, dict):
            # Direct lookup
            if key in data:
                return data[key]

            # Try nested lookup with dot notation
            if '.' in key:
                parts = key.split('.')
                current = data
                for part in parts:
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        return None
                return current

            # Search in nested dicts
            for v in data.values():
                result = self._find_value_in_data(key, v)
                if result is not None:
                    return result

        return None

    def _get_source_type(self, source_id: str, data_context: DataContext) -> str:
        """Determine the type of a source."""
        # This would typically come from configuration
        return "unknown"

    def _cross_validate(
        self,
        dp_config: DataPointConfig,
        source_values: list[DataPointValue]
    ) -> DataPointValidation:
        """Compare values across sources based on validation type."""

        validation_type = ValidationType(dp_config.validation.value)

        # Handle empty or single source cases
        if len(source_values) == 0:
            return DataPointValidation(
                data_point_id=dp_config.id,
                description=dp_config.description,
                validation_type=validation_type,
                status=ValidationStatus.MISSING,
                source_values=[],
                canonical_value=None,
                canonical_source=None,
                conflict_details="Not found in any source"
            )

        if len(source_values) == 1:
            return DataPointValidation(
                data_point_id=dp_config.id,
                description=dp_config.description,
                validation_type=validation_type,
                status=ValidationStatus.SINGLE_SOURCE,
                source_values=source_values,
                canonical_value=source_values[0].value,
                canonical_source=source_values[0].source_id,
                conflict_details=None
            )

        # Validate based on type
        match validation_type:
            case ValidationType.EXACT_MATCH:
                return self._validate_exact_match(dp_config, source_values)
            case ValidationType.FUZZY_MATCH:
                return self._validate_fuzzy_match(dp_config, source_values)
            case ValidationType.NUMERIC_EXACT:
                return self._validate_numeric_exact(dp_config, source_values)
            case ValidationType.NUMERIC_TOLERANCE:
                return self._validate_numeric_tolerance(
                    dp_config,
                    source_values,
                    dp_config.tolerance
                )
            case ValidationType.LIST_MATCH:
                return self._validate_list_match(dp_config, source_values)
            case _:
                return self._validate_exact_match(dp_config, source_values)

    def _validate_exact_match(
        self,
        dp_config: DataPointConfig,
        source_values: list[DataPointValue]
    ) -> DataPointValidation:
        """Validate that all values are exactly the same."""
        values = [sv.value for sv in source_values]

        # Normalize strings for comparison
        normalized = []
        for v in values:
            if isinstance(v, str):
                normalized.append(v.strip().lower())
            else:
                normalized.append(v)

        all_match = len(set(str(n) for n in normalized)) == 1

        if all_match:
            best_source = max(source_values, key=lambda sv: sv.confidence)
            return DataPointValidation(
                data_point_id=dp_config.id,
                description=dp_config.description,
                validation_type=ValidationType.EXACT_MATCH,
                status=ValidationStatus.VALIDATED,
                source_values=source_values,
                canonical_value=best_source.value,
                canonical_source=best_source.source_id,
                conflict_details=None
            )
        else:
            return DataPointValidation(
                data_point_id=dp_config.id,
                description=dp_config.description,
                validation_type=ValidationType.EXACT_MATCH,
                status=ValidationStatus.CONFLICT,
                source_values=source_values,
                canonical_value=None,
                canonical_source=None,
                conflict_details=f"Values differ: {values}"
            )

    def _validate_fuzzy_match(
        self,
        dp_config: DataPointConfig,
        source_values: list[DataPointValue]
    ) -> DataPointValidation:
        """Validate with fuzzy string matching."""
        values = [str(sv.value).strip() for sv in source_values]

        # Check pairwise similarity
        min_similarity = 1.0
        for i in range(len(values)):
            for j in range(i + 1, len(values)):
                similarity = SequenceMatcher(
                    None,
                    values[i].lower(),
                    values[j].lower()
                ).ratio()
                min_similarity = min(min_similarity, similarity)

        if min_similarity >= 0.85:  # 85% similarity threshold
            best_source = max(source_values, key=lambda sv: sv.confidence)
            return DataPointValidation(
                data_point_id=dp_config.id,
                description=dp_config.description,
                validation_type=ValidationType.FUZZY_MATCH,
                status=ValidationStatus.VALIDATED,
                source_values=source_values,
                canonical_value=best_source.value,
                canonical_source=best_source.source_id,
                conflict_details=None
            )
        else:
            return DataPointValidation(
                data_point_id=dp_config.id,
                description=dp_config.description,
                validation_type=ValidationType.FUZZY_MATCH,
                status=ValidationStatus.CONFLICT,
                source_values=source_values,
                canonical_value=None,
                canonical_source=None,
                conflict_details=f"Values differ (similarity: {min_similarity:.1%}): {values}"
            )

    def _validate_numeric_exact(
        self,
        dp_config: DataPointConfig,
        source_values: list[DataPointValue]
    ) -> DataPointValidation:
        """Validate that numeric values match exactly."""
        try:
            values = [float(sv.value) for sv in source_values]
        except (ValueError, TypeError):
            return self._validate_exact_match(dp_config, source_values)

        all_match = len(set(values)) == 1

        if all_match:
            best_source = max(source_values, key=lambda sv: sv.confidence)
            return DataPointValidation(
                data_point_id=dp_config.id,
                description=dp_config.description,
                validation_type=ValidationType.NUMERIC_EXACT,
                status=ValidationStatus.VALIDATED,
                source_values=source_values,
                canonical_value=best_source.value,
                canonical_source=best_source.source_id,
                conflict_details=None
            )
        else:
            return DataPointValidation(
                data_point_id=dp_config.id,
                description=dp_config.description,
                validation_type=ValidationType.NUMERIC_EXACT,
                status=ValidationStatus.CONFLICT,
                source_values=source_values,
                canonical_value=None,
                canonical_source=None,
                conflict_details=f"Values differ: {values}"
            )

    def _validate_numeric_tolerance(
        self,
        dp_config: DataPointConfig,
        source_values: list[DataPointValue],
        tolerance: float
    ) -> DataPointValidation:
        """Validate that numeric values are within tolerance."""
        try:
            values = [float(sv.value) for sv in source_values]
        except (ValueError, TypeError):
            return self._validate_exact_match(dp_config, source_values)

        if not values:
            return self._missing_validation(dp_config, source_values)

        max_val = max(values)
        min_val = min(values)

        if max_val == 0:
            deviation = 0.0
        else:
            deviation = (max_val - min_val) / max_val

        if deviation <= tolerance:
            best_source = max(source_values, key=lambda sv: sv.confidence)
            return DataPointValidation(
                data_point_id=dp_config.id,
                description=dp_config.description,
                validation_type=ValidationType.NUMERIC_TOLERANCE,
                status=ValidationStatus.VALIDATED,
                source_values=source_values,
                canonical_value=best_source.value,
                canonical_source=best_source.source_id,
                conflict_details=None,
                max_deviation=deviation
            )
        else:
            return DataPointValidation(
                data_point_id=dp_config.id,
                description=dp_config.description,
                validation_type=ValidationType.NUMERIC_TOLERANCE,
                status=ValidationStatus.CONFLICT,
                source_values=source_values,
                canonical_value=None,
                canonical_source=None,
                conflict_details=f"Values differ by {deviation:.1%}: {values}",
                max_deviation=deviation
            )

    def _validate_list_match(
        self,
        dp_config: DataPointConfig,
        source_values: list[DataPointValue]
    ) -> DataPointValidation:
        """Validate that lists contain the same items."""
        lists = []
        for sv in source_values:
            if isinstance(sv.value, list):
                lists.append(set(str(item) for item in sv.value))
            elif isinstance(sv.value, str):
                # Try to parse as comma-separated
                items = [item.strip() for item in sv.value.split(',')]
                lists.append(set(items))
            else:
                lists.append({str(sv.value)})

        # Check if all lists are equal
        if len(lists) > 0 and all(l == lists[0] for l in lists):
            best_source = max(source_values, key=lambda sv: sv.confidence)
            return DataPointValidation(
                data_point_id=dp_config.id,
                description=dp_config.description,
                validation_type=ValidationType.LIST_MATCH,
                status=ValidationStatus.VALIDATED,
                source_values=source_values,
                canonical_value=best_source.value,
                canonical_source=best_source.source_id,
                conflict_details=None
            )
        else:
            return DataPointValidation(
                data_point_id=dp_config.id,
                description=dp_config.description,
                validation_type=ValidationType.LIST_MATCH,
                status=ValidationStatus.CONFLICT,
                source_values=source_values,
                canonical_value=None,
                canonical_source=None,
                conflict_details=f"Lists differ: {[list(l) for l in lists]}"
            )

    def _missing_validation(
        self,
        dp_config: DataPointConfig,
        source_values: list[DataPointValue]
    ) -> DataPointValidation:
        """Create a missing validation result."""
        return DataPointValidation(
            data_point_id=dp_config.id,
            description=dp_config.description,
            validation_type=ValidationType.EXACT_MATCH,
            status=ValidationStatus.MISSING,
            source_values=source_values,
            canonical_value=None,
            canonical_source=None,
            conflict_details="Value not found or invalid"
        )
