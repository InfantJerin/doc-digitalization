#!/usr/bin/env python3
"""Detect heading-like lines with legal document patterns."""

from __future__ import annotations

import json
import re
import sys

import fitz

PATTERNS = [
    (re.compile(r"^ARTICLE\s+[IVX]+", re.IGNORECASE), 1),
    (re.compile(r"^Section\s+\d+\.\d+", re.IGNORECASE), 2),
    (re.compile(r"^SECTION\s+\d+\.\d+", re.IGNORECASE), 2),
    (re.compile(r"^SCHEDULE\s+", re.IGNORECASE), 1),
    (re.compile(r"^EXHIBIT\s+[A-Z]", re.IGNORECASE), 1),
    (re.compile(r"^APPENDIX\s+[A-Z]", re.IGNORECASE), 1),
]


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: detect_headings.py <pdf-path>", file=sys.stderr)
        return 1

    path = sys.argv[1]
    headings = []

    with fitz.open(path) as doc:
        for page_number in range(1, len(doc) + 1):
            text = doc[page_number - 1].get_text()
            for raw_line in text.splitlines():
                line = raw_line.strip()
                if len(line) < 4:
                    continue
                for pattern, level in PATTERNS:
                    if pattern.match(line):
                        headings.append(
                            {
                                "title": line,
                                "page": page_number,
                                "level": level,
                            }
                        )
                        break

    print(json.dumps({"headings": headings}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
