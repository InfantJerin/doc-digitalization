#!/usr/bin/env python3
"""Merge per-document field extraction outputs."""

from __future__ import annotations

import json
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: merge_results.py <result-json> [<result-json> ...]", file=sys.stderr)
        return 1

    merged: dict[str, dict] = {}

    for raw in sys.argv[1:]:
        payload = json.loads(raw)
        for field in payload.get("fields", []):
            field_path = field.get("field_path")
            if not field_path:
                continue
            current = merged.get(field_path)
            if not current or field.get("confidence", 0.0) > current.get("confidence", 0.0):
                merged[field_path] = field

    print(json.dumps({"fields": list(merged.values())}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
