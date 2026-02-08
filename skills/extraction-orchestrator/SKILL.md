---
name: extraction-orchestrator
description: "Meta-skill for config-driven extraction. Builds field execution plans, dispatches field extractor skills, and merges multi-document outputs with citation confidence ranking."
---

# Extraction Orchestrator Skill

Use this skill when a pipeline config defines extraction fields and document sources.

## Workflow
1. Parse pipeline config and produce an extraction plan ordered by likely section relevance.
2. For each field, resolve and load the corresponding field skill from `skills/field-extractors/`.
3. Use structure hints (`likely_sections`) before reading large page ranges.
4. Always return structured output for every configured field, even when value is `null`.
5. Merge multi-document outputs by highest confidence while preserving citations.

## Scripts
- `scripts/plan_extraction.py`: Convert pipeline YAML into deterministic execution plan JSON.
- `scripts/merge_results.py`: Merge extracted field outputs from multiple documents.
