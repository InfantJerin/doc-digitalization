from src.agent.orchestrator import AgentOrchestrator
from src.core.config_loader import FieldSchemaConfig, FieldStrategyConfig


def test_strategy_resolution_prefers_explicit_field_strategy():
    orchestrator = AgentOrchestrator()
    field = FieldSchemaConfig(type="string", field_strategy=FieldStrategyConfig.SKILL, cross_validate=True)
    assert orchestrator._resolve_strategy(field) == FieldStrategyConfig.SKILL


def test_strategy_resolution_uses_cross_validate_flag_when_no_explicit_strategy():
    orchestrator = AgentOrchestrator()
    field = FieldSchemaConfig(type="string", cross_validate=True)
    assert orchestrator._resolve_strategy(field) == FieldStrategyConfig.CROSS_VALIDATE


def test_strategy_resolution_defaults_to_direct():
    orchestrator = AgentOrchestrator()
    field = FieldSchemaConfig(type="string")
    assert orchestrator._resolve_strategy(field) == FieldStrategyConfig.DIRECT
