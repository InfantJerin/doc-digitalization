#!/usr/bin/env python3
"""Detect probable table-of-contents lines from early pages."""

from __future__ import annotations

import json
import re
import sys

import fitz

TOC_LINE_RE = re.compile(r"^(?:article|section|schedule|exhibit|appendix).+\.{2,}\s*\d+\s*$", re.IGNORECASE)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: detect_toc.py <pdf-path>", file=sys.stderr)
        return 1

    path = sys.argv[1]
    candidates = []

    with fitz.open(path) as doc:
        for page_number in range(1, min(16, len(doc) + 1)):
            text = doc[page_number - 1].get_text()
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            matched = [line for line in lines if TOC_LINE_RE.match(line)]
            if matched:
                candidates.append(
                    {
                        "page": page_number,
                        "lines": matched,
                    }
                )

    print(
        json.dumps(
            {
                "has_toc": bool(candidates),
                "toc_pages": [entry["page"] for entry in candidates],
                "toc_candidates": candidates,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
