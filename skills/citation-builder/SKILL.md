---
name: citation-builder
description: "Build and validate extraction citations by locating quote bounding boxes and verifying cited text on the target page."
---

# Citation Builder Skill

Use this skill after field extraction to produce UI-grade citations.

## Workflow
1. Run `scripts/find_bounding_box.py` with `pdf_path`, `page_number`, and quoted text.
2. Run `scripts/validate_citation.py` to ensure quote exists on cited page.
3. If validation fails, retry with shortened quote segments before returning citation.
