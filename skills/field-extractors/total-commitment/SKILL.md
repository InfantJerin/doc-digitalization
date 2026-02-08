---
name: total-commitment
description: "Extract total commitment amount and currency from commitments schedules and facility terms."
---

# total-commitment

Use this skill when extracting the `total-commitment` field.

## Extraction Rules
1. Prioritize occurrences in configured `likely_sections` before broad search.
2. Capture the most explicit numeric/date/legal value, not examples or references.
3. Include citation quote text that uniquely supports the extracted value.
4. If conflicting values exist, prefer the clause with binding covenant language and note ambiguity.
5. Return `null` with confidence `0` when no authoritative evidence is present.
