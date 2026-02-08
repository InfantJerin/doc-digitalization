---
name: structure-analyzer
description: "Extract document structure using a four-step fallback strategy: PDF bookmarks, TOC detection, heading detection, then content-based fallback for large legal documents."
---

# Structure Analyzer Skill

Use this skill for long documents (100+ pages) before field extraction.

## Strategy Order
1. Run `scripts/extract_bookmarks.py` for native PDF outline.
2. If no outline exists, run `scripts/detect_toc.py` on first pages.
3. If TOC is weak, run `scripts/detect_headings.py` for legal heading patterns.
4. Build canonical section tree with `scripts/build_structure_tree.py`.

## Reference
- Pattern file: `references/heading_patterns.md`
