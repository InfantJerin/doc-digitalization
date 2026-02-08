#!/usr/bin/env python3
"""Validate that a quoted string appears on a cited page."""

from __future__ import annotations

import json
import re
import sys

import fitz


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: validate_citation.py <pdf-path> <page-number> <quote>", file=sys.stderr)
        return 1

    pdf_path = sys.argv[1]
    page_number = int(sys.argv[2])
    quote = sys.argv[3]

    with fitz.open(pdf_path) as doc:
        page_text = doc[page_number - 1].get_text()

    quote_norm = normalize(quote)
    page_norm = normalize(page_text)

    valid = quote_norm in page_norm if quote_norm else False
    confidence = 1.0 if valid else 0.0

    if not valid and len(quote_norm.split()) >= 4:
        partial = " ".join(quote_norm.split()[:4])
        if partial in page_norm:
            valid = True
            confidence = 0.75

    print(json.dumps({"valid": valid, "confidence": confidence}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
