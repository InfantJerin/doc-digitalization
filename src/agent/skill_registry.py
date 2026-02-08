"""Skill discovery and metadata indexing."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass(slots=True)
class SkillDefinition:
    """Metadata and paths for a discovered skill."""

    name: str
    description: str
    directory: Path
    skill_file: Path
    body: str
    scripts: list[Path] = field(default_factory=list)
    references: list[Path] = field(default_factory=list)

    def compact_summary(self, max_chars: int = 220) -> str:
        summary = self.description.strip().replace("\n", " ")
        if len(summary) > max_chars:
            summary = summary[: max_chars - 3].rstrip() + "..."
        return f"{self.name}: {summary}"


class SkillRegistry:
    """Discovers skills and provides fast lookup by name."""

    def __init__(self, skills_root: Path):
        self.skills_root = Path(skills_root)
        self._skills: dict[str, SkillDefinition] = {}

    def discover(self) -> dict[str, SkillDefinition]:
        """Scan the skills directory recursively and index `SKILL.md` files."""
        skills: dict[str, SkillDefinition] = {}
        if not self.skills_root.exists():
            self._skills = {}
            return self._skills

        for skill_file in self.skills_root.rglob("SKILL.md"):
            parsed = self._parse_skill_file(skill_file)
            if not parsed:
                continue

            metadata, body = parsed
            name = str(metadata.get("name", "")).strip()
            description = str(metadata.get("description", "")).strip()
            if not name:
                # Fallback to folder name for resilience.
                name = skill_file.parent.name
            if not description:
                description = "No description provided"

            skill_dir = skill_file.parent
            definition = SkillDefinition(
                name=name,
                description=description,
                directory=skill_dir,
                skill_file=skill_file,
                body=body.strip(),
                scripts=sorted([p for p in (skill_dir / "scripts").glob("**/*") if p.is_file()])
                if (skill_dir / "scripts").exists()
                else [],
                references=sorted([p for p in (skill_dir / "references").glob("**/*") if p.is_file()])
                if (skill_dir / "references").exists()
                else [],
            )
            skills[definition.name] = definition

        self._skills = skills
        return self._skills

    def ensure_discovered(self) -> None:
        if not self._skills:
            self.discover()

    def get(self, skill_name: str) -> Optional[SkillDefinition]:
        self.ensure_discovered()
        return self._skills.get(skill_name)

    def get_compact_index(self, max_skills: int = 128) -> list[str]:
        self.ensure_discovered()
        skills = sorted(self._skills.values(), key=lambda item: item.name)
        return [skill.compact_summary() for skill in skills[:max_skills]]

    def all(self) -> dict[str, SkillDefinition]:
        self.ensure_discovered()
        return dict(self._skills)

    def resolve_field_skill(self, skill_name: str) -> Optional[SkillDefinition]:
        """
        Resolve extractor skill names with or without `field-extractors/` prefix.
        """
        self.ensure_discovered()
        direct = self._skills.get(skill_name)
        if direct:
            return direct

        alt_key = f"field-extractors/{skill_name}"
        return self._skills.get(alt_key)

    def _parse_skill_file(self, path: Path) -> Optional[tuple[dict, str]]:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return None

        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            # No frontmatter is invalid for this project migration.
            return None

        end_idx = None
        for idx in range(1, len(lines)):
            if lines[idx].strip() == "---":
                end_idx = idx
                break

        if end_idx is None:
            return None

        frontmatter = "\n".join(lines[1:end_idx])
        body = "\n".join(lines[end_idx + 1 :])
        metadata = yaml.safe_load(frontmatter) or {}
        if not isinstance(metadata, dict):
            return None
        return metadata, body
