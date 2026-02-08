#!/usr/bin/env python3
"""Validate leverage ratio extraction payload."""

from __future__ import annotations

import json
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_leverage_ratio.py <json-payload>", file=sys.stderr)
        return 1

    payload = json.loads(sys.argv[1])
    errors = []

    current_ratio = payload.get("current_ratio")
    covenant_max = payload.get("covenant_max")

    if current_ratio is None:
        errors.append("current_ratio is required")
    if covenant_max is None:
        errors.append("covenant_max is required")

    if isinstance(current_ratio, (int, float)) and isinstance(covenant_max, (int, float)):
        computed = current_ratio <= covenant_max
        provided = payload.get("in_compliance")
        if provided is not None and bool(provided) != computed:
            errors.append("in_compliance does not match current_ratio <= covenant_max")

    print(
        json.dumps(
            {
                "valid": not errors,
                "errors": errors,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
