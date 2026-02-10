# Document Digitalization Platform

Agent-first platform for document extraction and document generation, with a skills-based extraction architecture, model-agnostic LLM integrations, and review workflow support.

## What Changed

This codebase now includes:

- Hybrid extraction strategy per field (`direct`, `skill`, `cross_validate`)
- Skills library under `skills/` with orchestrator/structure/field/citation skills
- Model-agnostic LLM runtime (`openai_compatible`, `litellm`, `anthropic`)
- OpenAI API-spec compatible integration with configurable `base_url`
- Agent orchestration layer under `src/agent/`
- Repository-backed persistence layer under `src/database/`
- Health/readiness API endpoints

## Core Capabilities

### Extraction

- Config-driven extraction from `config/pipelines/extraction/*.yaml`
- Page-index-first retrieval for large documents
- Field-level routing strategy:
  - `direct`: structured extraction for simple fields
  - `skill`: skill-guided extraction for complex/high-risk fields
  - `cross_validate`: multi-document reconciliation
- Citation enrichment with quote and bounding box support

### Generation

- Template-based generation from `config/pipelines/generation/*.yaml`
- Data gathering + cross-source validation for data points
- Section-level generation/regeneration

### Workflow

- Review tasks and attestations
- Override support with justification
- Status lifecycle (`processing`, `awaiting_review`, `approved`, etc.)

## Project Structure

```text
doc-digitalization/
├── config/
│   └── pipelines/
│       ├── extraction/
│       └── generation/
├── skills/
│   ├── extraction-orchestrator/
│   ├── structure-analyzer/
│   ├── field-extractors/
│   └── citation-builder/
├── src/
│   ├── agent/
│   ├── api/
│   ├── core/
│   ├── database/
│   ├── extraction/
│   ├── generation/
│   ├── integrations/
│   ├── tools/
│   ├── workers/
│   └── workflow/
├── tests/
└── pyproject.toml
```

## Local Setup

### Prerequisites

- Python 3.11+
- Docker (optional)

### Install

```bash
git clone <repository-url>
cd doc-digitalization

python -m venv .venv
source .venv/bin/activate

pip install -U pip
pip install -e ".[dev]"
```

Optional provider packages:

```bash
# Claude Agent SDK extras (optional)
pip install -e ".[agent-sdk]"
```

### Environment

Create `.env` from `.env.example`:

```bash
cp .env.example .env
```

Minimum fields to set depend on provider.

#### OpenAI-compatible endpoint (recommended)

```env
LLM_PROVIDER=openai_compatible
LLM_API_BASE=https://your-openai-compatible-endpoint/v1
LLM_API_KEY=your-key
AGENT_MODEL=gpt-4.1-mini
```

#### LiteLLM

```env
LLM_PROVIDER=litellm
LLM_API_BASE=
LLM_API_KEY=your-key
AGENT_MODEL=<provider-model-id>
```

#### Anthropic

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-key
AGENT_MODEL=claude-sonnet-4-20250514
```

## Run

### API

```bash
uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

### Worker (optional)

```bash
python -m src.workers.extraction_worker
```

### Docker Compose

```bash
docker compose up --build
```

## API Docs and Health

- Swagger: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/v1/health`
- Readiness: `http://localhost:8000/api/v1/health/readiness`

## Extraction Strategy Configuration

Example field config with strategy:

```yaml
extraction_schema:
  borrower:
    type: object
    field_strategy: direct
    likely_sections: ["Preamble", "Definitions"]

  financial_covenants:
    type: array
    field_strategy: skill
    likely_sections: ["Financial Covenants", "Article VII"]

  amendment_threshold:
    type: object
    field_strategy: cross_validate
    cross_validate: true
```

If `field_strategy` is omitted, defaults are:

1. `cross_validate` when `cross_validate: true`
2. `skill` when explicit `skill` is configured
3. otherwise `direct`

## Tests

```bash
python -m pytest
```

Targeted suites:

```bash
python -m pytest tests/unit
python -m pytest tests/skills
python -m pytest tests/integration
```

## Smoke Test (Sample Credit Agreement)

You can run a real extraction smoke test directly against the sample PDF in `resources/`.

```bash
python scripts/smoke_test_extraction.py \
  --pipeline-id credit-agreement \
  --document-path "resources/credit agreement/AbbieVie Term Loan Credit Agreement.pdf" \
  --output ./smoke_extraction_output.json
```

What this does:

- Runs `ExtractionService` end-to-end
- Uses a local file-backed DMS adapter (no external DMS required)
- Prints JSON result to stdout
- Optionally writes output JSON to the path passed in `--output`

## Notes

- `skills/` files are validated via tests (`tests/skills/test_skill_format.py`).
- Agent orchestration is provider-agnostic through `src/integrations/llm_factory.py`.
- OpenAI-spec format is supported through `openai_compatible` mode and `LLM_API_BASE`.

## License

Proprietary - All rights reserved.
