from __future__ import annotations

import re
from pathlib import Path

import yaml


def parse_frontmatter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines and lines[0].strip() == "---", f"Missing frontmatter start: {path}"

    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    assert end_idx is not None, f"Missing frontmatter end: {path}"

    metadata = yaml.safe_load("\n".join(lines[1:end_idx])) or {}
    body = "\n".join(lines[end_idx + 1 :])
    return metadata, body


def test_all_skill_files_have_required_frontmatter():
    skill_files = sorted(Path("skills").rglob("SKILL.md"))
    assert skill_files, "No SKILL.md files found"

    for path in skill_files:
        metadata, _ = parse_frontmatter(path)
        assert metadata.get("name"), f"Missing name in {path}"
        assert metadata.get("description"), f"Missing description in {path}"


def test_skill_script_references_exist():
    skill_files = sorted(Path("skills").rglob("SKILL.md"))
    script_pattern = re.compile(r"scripts/[A-Za-z0-9_.-]+")

    for path in skill_files:
        _, body = parse_frontmatter(path)
        for relative in script_pattern.findall(body):
            script_path = path.parent / relative
            assert script_path.exists(), f"Referenced script missing: {script_path}"
