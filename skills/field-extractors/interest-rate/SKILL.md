---
name: interest-rate
description: "Extract base margin, benchmark margin, and default rate spread from pricing provisions."
---

# interest-rate

Use this skill when extracting the `interest-rate` field.

## Extraction Rules
1. Prioritize occurrences in configured `likely_sections` before broad search.
2. Capture the most explicit numeric/date/legal value, not examples or references.
3. Include citation quote text that uniquely supports the extracted value.
4. If conflicting values exist, prefer the clause with binding covenant language and note ambiguity.
5. Return `null` with confidence `0` when no authoritative evidence is present.
