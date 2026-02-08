#!/usr/bin/env python3
"""Locate a quote bounding box on a specific PDF page."""

from __future__ import annotations

import json
import sys

import fitz


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: find_bounding_box.py <pdf-path> <page-number> <quote>", file=sys.stderr)
        return 1

    pdf_path = sys.argv[1]
    page_number = int(sys.argv[2])
    quote = sys.argv[3]

    with fitz.open(pdf_path) as doc:
        page = doc[page_number - 1]
        instances = page.search_for(quote)

    if not instances:
        print(json.dumps({"found": False, "bounding_box": None}, indent=2))
        return 0

    rect = instances[0]
    print(
        json.dumps(
            {
                "found": True,
                "bounding_box": {
                    "x": rect.x0,
                    "y": rect.y0,
                    "width": rect.width,
                    "height": rect.height,
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
