# Document Digitalization Platform

A platform for extracting structured data from documents and generating documents from templates and multiple data sources.

## Features

### Extraction Pipeline
- **Single and Multi-Document Extraction**: Extract data from one or multiple related documents
- **Large Document Handling**: Hierarchical structure detection for documents 100+ pages
- **Citation Tracking**: Link every extracted value to its source (page, location)
- **Maker-Checker Workflow**: Review, attest, and override extracted values
- **Revision History**: Track changes across versions

### Generation Pipeline
- **Template-Based Generation**: Define document structure via YAML
- **Multi-Source Data**: Gather data from APIs, documents, databases
- **Data Point Validation**: Cross-validate facts across sources, flag conflicts
- **Section Regeneration**: Regenerate individual sections with feedback

## Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose (optional, for local infrastructure)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd doc-digitalization

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export ANTHROPIC_API_KEY="your-api-key"
```

### Running Locally

```bash
# Start the API server
uvicorn src.api.app:app --reload

# Or with Docker Compose
docker-compose up -d
```

### API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Configuration

Pipelines are configured via YAML files in `config/pipelines/`:

### Extraction Pipeline Example

```yaml
extraction_use_case:
  id: "covenant-compliance"
  name: "Covenant Compliance Extraction"

  document_types:
    - type: compliance_certificate
      required: true

  extraction_schema:
    leverage_ratio:
      type: object
      properties:
        current_ratio: { type: number }
        covenant_max: { type: number }
      likely_sections: ["Financial Covenants"]
```

### Generation Pipeline Example

```yaml
generation_pipeline:
  id: "credit-memo-generator"
  name: "Credit Memo Generator"

  data_sources:
    deal_info:
      type: api
      endpoint: "https://api/deals/{deal_id}"

  template:
    sections:
      - id: executive_summary
        name: "Executive Summary"
        instructions: "Write a summary..."
        data_points:
          - id: borrower_name
            sources: [deal_info]
            validation: fuzzy_match
```

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture documentation.

```
┌─────────────────────────────────────────────────────────────────┐
│                     API Layer (FastAPI)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐           ┌─────────────────┐              │
│  │   Extraction    │           │   Generation    │              │
│  │    Service      │           │    Service      │              │
│  └────────┬────────┘           └────────┬────────┘              │
│           │                             │                        │
│           └──────────┬──────────────────┘                        │
│                      │                                           │
│           ┌──────────┴──────────┐                               │
│           │  Workflow Service   │                               │
│           │  (Maker-Checker)    │                               │
│           └─────────────────────┘                               │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│  Integrations: DMS | Claude | Webhooks                          │
└─────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
doc-digitalization/
├── config/
│   └── pipelines/
│       ├── extraction/     # Extraction pipeline configs
│       └── generation/     # Generation pipeline configs
├── src/
│   ├── core/               # Models, config, exceptions
│   ├── extraction/         # Extraction pipeline
│   ├── generation/         # Generation pipeline
│   ├── workflow/           # Review workflow
│   ├── integrations/       # External services
│   └── api/                # FastAPI routes
├── docs/                   # Documentation
├── tests/                  # Test suite
└── infrastructure/         # Terraform, K8s configs
```

## API Endpoints

### Extraction
- `POST /api/v1/extractions` - Trigger extraction
- `GET /api/v1/extractions/{run_id}` - Get extraction results
- `POST /api/v1/extractions/{run_id}/rerun` - Re-run extraction

### Generation
- `POST /api/v1/generations` - Trigger generation
- `GET /api/v1/generations/{run_id}` - Get generation results
- `POST /api/v1/generations/{run_id}/sections/{section_id}/regenerate` - Regenerate section
- `GET /api/v1/generations/{run_id}/download` - Download document

### Review
- `GET /api/v1/reviews` - List review tasks
- `GET /api/v1/reviews/{task_id}` - Get review data
- `POST /api/v1/reviews/{task_id}/attest` - Submit attestation

## Development

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=src

# Type checking
mypy src

# Linting
ruff check src

# Formatting
black src
isort src
```

## License

Proprietary - All rights reserved.
