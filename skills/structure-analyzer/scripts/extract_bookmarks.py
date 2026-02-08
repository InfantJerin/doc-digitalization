#!/usr/bin/env python3
"""Extract PDF bookmark outline entries."""

from __future__ import annotations

import json
import sys

import fitz


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: extract_bookmarks.py <pdf-path>", file=sys.stderr)
        return 1

    path = sys.argv[1]
    with fitz.open(path) as doc:
        toc = doc.get_toc()

    entries = [
        {
            "level": level,
            "title": title.strip(),
            "page": page,
        }
        for level, title, page in toc
        if title.strip()
    ]
    print(json.dumps({"bookmarks": entries}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
