"""
Tests for Data Point Validator.
"""

import pytest
from unittest.mock import Mock

from src.generation.data_point_validator import (
    DataPointValidator,
    DataContext,
)
from src.core.models import (
    DataPointValue,
    ValidationStatus,
    ValidationType,
)
from src.core.config_loader import DataPointConfig, ValidationTypeConfig


class TestDataPointValidator:
    """Tests for DataPointValidator."""

    @pytest.fixture
    def validator(self):
        """Create a validator instance."""
        return DataPointValidator(default_tolerance=0.05)

    def test_validate_exact_match_success(self, validator):
        """Test exact match validation when values match."""
        source_values = [
            DataPointValue(source_id="api", source_type="api", value="Acme Corp", confidence=1.0),
            DataPointValue(source_id="doc", source_type="dms", value="Acme Corp", confidence=0.9),
        ]

        dp_config = DataPointConfig(
            id="company_name",
            description="Company name",
            sources=["api", "doc"],
            validation=ValidationTypeConfig.EXACT_MATCH
        )

        result = validator._validate_exact_match(dp_config, source_values)

        assert result.status == ValidationStatus.VALIDATED
        assert result.canonical_value == "Acme Corp"

    def test_validate_exact_match_conflict(self, validator):
        """Test exact match validation when values differ."""
        source_values = [
            DataPointValue(source_id="api", source_type="api", value="Acme Corp", confidence=1.0),
            DataPointValue(source_id="doc", source_type="dms", value="Acme Corporation", confidence=0.9),
        ]

        dp_config = DataPointConfig(
            id="company_name",
            description="Company name",
            sources=["api", "doc"],
            validation=ValidationTypeConfig.EXACT_MATCH
        )

        result = validator._validate_exact_match(dp_config, source_values)

        assert result.status == ValidationStatus.CONFLICT
        assert result.canonical_value is None
        assert "differ" in result.conflict_details.lower()

    def test_validate_fuzzy_match_success(self, validator):
        """Test fuzzy match validation with minor variations."""
        source_values = [
            DataPointValue(source_id="api", source_type="api", value="Acme Corporation", confidence=1.0),
            DataPointValue(source_id="doc", source_type="dms", value="Acme Corp.", confidence=0.9),
        ]

        dp_config = DataPointConfig(
            id="company_name",
            description="Company name",
            sources=["api", "doc"],
            validation=ValidationTypeConfig.FUZZY_MATCH
        )

        result = validator._validate_fuzzy_match(dp_config, source_values)

        # With fuzzy matching, these should be considered a match
        # (similarity > 0.85)
        assert result.status == ValidationStatus.VALIDATED

    def test_validate_numeric_tolerance_success(self, validator):
        """Test numeric tolerance validation within threshold."""
        source_values = [
            DataPointValue(source_id="api", source_type="api", value=100.0, confidence=1.0),
            DataPointValue(source_id="doc", source_type="dms", value=102.0, confidence=0.9),
        ]

        dp_config = DataPointConfig(
            id="amount",
            description="Amount",
            sources=["api", "doc"],
            validation=ValidationTypeConfig.NUMERIC_TOLERANCE,
            tolerance=0.05  # 5% tolerance
        )

        result = validator._validate_numeric_tolerance(dp_config, source_values, 0.05)

        assert result.status == ValidationStatus.VALIDATED
        assert result.max_deviation < 0.05

    def test_validate_numeric_tolerance_conflict(self, validator):
        """Test numeric tolerance validation exceeding threshold."""
        source_values = [
            DataPointValue(source_id="api", source_type="api", value=100.0, confidence=1.0),
            DataPointValue(source_id="doc", source_type="dms", value=110.0, confidence=0.9),
        ]

        dp_config = DataPointConfig(
            id="amount",
            description="Amount",
            sources=["api", "doc"],
            validation=ValidationTypeConfig.NUMERIC_TOLERANCE,
            tolerance=0.05  # 5% tolerance, but diff is 10%
        )

        result = validator._validate_numeric_tolerance(dp_config, source_values, 0.05)

        assert result.status == ValidationStatus.CONFLICT
        assert result.max_deviation > 0.05

    def test_single_source_status(self, validator):
        """Test that single source returns SINGLE_SOURCE status."""
        source_values = [
            DataPointValue(source_id="api", source_type="api", value="Test", confidence=1.0),
        ]

        dp_config = DataPointConfig(
            id="test",
            description="Test",
            sources=["api"],
            validation=ValidationTypeConfig.EXACT_MATCH
        )

        result = validator._cross_validate(dp_config, source_values)

        assert result.status == ValidationStatus.SINGLE_SOURCE
        assert result.canonical_value == "Test"

    def test_missing_status(self, validator):
        """Test that no sources returns MISSING status."""
        source_values = []

        dp_config = DataPointConfig(
            id="test",
            description="Test",
            sources=["api"],
            validation=ValidationTypeConfig.EXACT_MATCH
        )

        result = validator._cross_validate(dp_config, source_values)

        assert result.status == ValidationStatus.MISSING
        assert result.canonical_value is None

    def test_validate_list_match_success(self, validator):
        """Test list match validation when lists are equal."""
        source_values = [
            DataPointValue(source_id="api", source_type="api", value=["A", "B", "C"], confidence=1.0),
            DataPointValue(source_id="doc", source_type="dms", value=["B", "C", "A"], confidence=0.9),
        ]

        dp_config = DataPointConfig(
            id="items",
            description="Items",
            sources=["api", "doc"],
            validation=ValidationTypeConfig.LIST_MATCH
        )

        result = validator._validate_list_match(dp_config, source_values)

        # Same items, different order - should match
        assert result.status == ValidationStatus.VALIDATED
