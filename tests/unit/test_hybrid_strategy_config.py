from src.core.config_loader import ConfigLoader, FieldStrategyConfig


def test_credit_agreement_field_strategies_parse():
    config = ConfigLoader("config/pipelines").load_extraction_pipeline("credit-agreement")

    assert config.extraction_schema["borrower"].field_strategy == FieldStrategyConfig.DIRECT
    assert config.extraction_schema["facility_type"].field_strategy == FieldStrategyConfig.SKILL
    assert config.extraction_schema["amendment_threshold"].field_strategy == FieldStrategyConfig.CROSS_VALIDATE


def test_default_strategy_is_none_when_not_set():
    # generation pipeline doesn't use this field schema; check via direct model creation path
    from src.core.config_loader import FieldSchemaConfig

    field = FieldSchemaConfig(type="string", description="x")
    assert field.field_strategy is None
