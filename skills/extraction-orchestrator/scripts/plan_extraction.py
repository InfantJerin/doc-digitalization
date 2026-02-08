#!/usr/bin/env python3
"""Build an extraction plan from pipeline YAML."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml


def slugify(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: plan_extraction.py <pipeline-yaml>", file=sys.stderr)
        return 1

    path = Path(sys.argv[1])
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    config = raw.get("extraction_use_case", raw)

    extraction_schema = config.get("extraction_schema", {})
    plan = {
        "pipeline_id": config.get("id"),
        "fields": [],
    }

    for field_name, spec in extraction_schema.items():
        plan["fields"].append(
            {
                "field_path": field_name,
                "skill": spec.get("skill") or slugify(field_name),
                "likely_sections": spec.get("likely_sections", []),
                "sources": spec.get("sources", []),
                "cross_validate": bool(spec.get("cross_validate", False)),
            }
        )

    print(json.dumps(plan, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
