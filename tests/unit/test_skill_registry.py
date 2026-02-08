from pathlib import Path

from src.agent.skill_registry import SkillRegistry


def test_skill_registry_discovers_project_skills():
    registry = SkillRegistry(Path("skills"))
    skills = registry.discover()

    assert "extraction-orchestrator" in skills
    assert "structure-analyzer" in skills
    assert "leverage-ratio" in skills


def test_skill_registry_compact_index_has_content():
    registry = SkillRegistry(Path("skills"))
    index = registry.get_compact_index()

    assert index
    assert any("extraction-orchestrator" in line for line in index)
