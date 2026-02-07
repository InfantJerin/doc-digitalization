# Document Digitalization Platform - Architecture Documentation

## Overview

This platform provides two main capabilities for document processing:

1. **Extraction Pipeline** - Extract structured data from documents (single or multi-document)
2. **Generation Pipeline** - Generate documents from templates and multiple data sources

Both pipelines support:
- Configuration via YAML files
- Maker-checker workflow with citations
- Multi-attestation by reviewers
- Revision tracking
- Audit trail

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     DOCUMENT DIGITALIZATION PLATFORM                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                           ┌─────────────────┐                               │
│                           │   CONFIG REPO   │                               │
│                           │   (YAML files)  │                               │
│                           └────────┬────────┘                               │
│                                    │                                         │
│  ┌──────────────┐                  │                  ┌──────────────┐      │
│  │     DMS      │                  │                  │   CHECKER    │      │
│  │   (Docs)     │◄────────────────►│◄────────────────►│     UI       │      │
│  └──────┬───────┘                  │                  └──────────────┘      │
│         │                          │                                         │
│         │         ┌────────────────┴────────────────┐                       │
│         │         │                                 │                        │
│         │         ▼                                 ▼                        │
│         │  ┌─────────────────┐             ┌─────────────────┐              │
│         │  │   EXTRACTION    │             │   GENERATION    │              │
│         └─►│    SERVICE      │             │    SERVICE      │◄─────┐       │
│            │                 │             │                 │      │       │
│            │ • Structure     │             │ • Data gather   │      │       │
│            │ • Extract       │             │ • Section gen   │      │       │
│            │ • Citations     │             │ • Assembly      │      │       │
│            └────────┬────────┘             └────────┬────────┘      │       │
│                     │                               │               │       │
│                     │         ┌─────────────────────┘               │       │
│                     │         │                                     │       │
│                     ▼         ▼                                     │       │
│            ┌─────────────────────────────┐                          │       │
│            │       WORKFLOW SERVICE       │                          │       │
│            │                             │                          │       │
│            │ • Review tasks              │                          │       │
│            │ • Attestations              │                          │       │
│            │ • Revisions                 │                          │       │
│            └──────────────┬──────────────┘                          │       │
│                           │                                         │       │
│                           ▼                                         │       │
│            ┌─────────────────────────────┐                          │       │
│            │      POST-SINK SERVICE      │                          │       │
│            │                             │                          │       │
│            │ • Webhooks                  │──────────────────────────┘       │
│            │ • Audit DB                  │  (extraction results feed        │
│            └─────────────────────────────┘   into generation)               │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  DATA LAYER                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  PostgreSQL  │  │      S3      │  │    Redis     │  │    Kafka     │     │
│  │              │  │              │  │              │  │              │     │
│  │ • Deals      │  │ • Documents  │  │ • Cache      │  │ • Events     │     │
│  │ • Runs       │  │ • Structures │  │ • Sessions   │  │ • Triggers   │     │
│  │ • Revisions  │  │ • Drafts     │  │              │  │              │     │
│  │ • Audits     │  │              │  │              │  │              │     │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  INFRASTRUCTURE: AWS (EKS, RDS, S3, MSK, ElastiCache)                       │
│  LOCAL DEV: Kubernetes (minikube/kind), LocalStack                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Extraction Pipeline

### Overview

The extraction pipeline extracts structured data from documents. It supports:
- Single document extraction
- Multi-document extraction (data spans multiple documents)
- Large document handling (600+ pages via hierarchical structure detection)

### Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EXTRACTION PIPELINE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  TRIGGER                                                                     │
│  ├── New document uploaded (via DMS)                                         │
│  ├── Manual re-run (Ops UI)                                                  │
│  └── Schema change (triggers re-extraction)                                  │
│                                                                              │
│  CONFIGURATION                                                               │
│  └── YAML files committed to repo → Developer tests → Deploys               │
│                                                                              │
│  DOCUMENT SOURCE                                                             │
│  └── DMS API: GET /deals/{deal_id}/documents → returns doc types + files    │
│                                                                              │
│  EXTRACTION                                                                  │
│  ├── Structure detection (hierarchical tree building)                        │
│  ├── Targeted section retrieval                                              │
│  └── Batch extraction with citations                                         │
│                                                                              │
│  REVIEW (Checker UI)                                                         │
│  ├── Side-by-side: PDF viewer | Extracted fields                            │
│  ├── Click field → Highlight in PDF (citation)                              │
│  ├── Low confidence flagged → Checker decides                               │
│  ├── Attest: Approve field value                                            │
│  └── Override: Change value + justification                                 │
│                                                                              │
│  MULTI-ATTEST                                                                │
│  └── 1-2 Ops review and attest fields                                       │
│                                                                              │
│  POST-SINK                                                                   │
│  ├── Webhook → Configured APIs                                               │
│  └── Store in DB (audit trail)                                              │
│                                                                              │
│  REVISIONS                                                                   │
│  ├── New doc uploaded → New revision                                         │
│  ├── Manual re-run → New revision                                           │
│  └── Schema change → New revision                                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Large Document Handling

For documents over 100 pages (e.g., credit agreements), we use hierarchical structure extraction:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 LARGE DOCUMENT EXTRACTION PIPELINE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STAGE 1: STRUCTURE DETECTION                                                │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Strategy 1: PDF native bookmarks (instant, no LLM)                  │    │
│  │  Strategy 2: TOC detection + parsing (LLM on first 15 pages)         │    │
│  │  Strategy 3: Heading detection via formatting (regex + font size)    │    │
│  │  Strategy 4: Content-based generation (LLM, most expensive)          │    │
│  │                                                                      │    │
│  │  Output: Hierarchical tree of sections with page ranges              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                   │                                          │
│                                   ▼                                          │
│  STAGE 2: SECTION-TO-FIELD MAPPING                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Map extraction fields to likely sections:                           │    │
│  │    leverage_ratio → ["Financial Covenants", "Definitions"]           │    │
│  │    borrower_name → ["Preamble", "Definitions"]                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                   │                                          │
│                                   ▼                                          │
│  STAGE 3: TARGETED EXTRACTION                                                │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Send only relevant sections to Claude (not full 600 pages)          │    │
│  │  Example: 65 pages instead of 600 for covenant extraction            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Generation Pipeline

### Overview

The generation pipeline creates documents from templates and multiple data sources.

### Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        GENERATION WORKFLOW                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. TRIGGER                                                                  │
│     POST /api/v1/generate                                                    │
│     { "pipeline_id": "credit-memo-generator", "deal_id": "LOAN-2024-001" }  │
│                                                                              │
│  2. DATA GATHERING                                                           │
│     For each data_source in template:                                        │
│       [API] → Fetch JSON from endpoint                                       │
│       [DMS] → Fetch documents → Extract structure → Get content              │
│       [Extraction Pipeline] → Get latest extraction results                  │
│                                                                              │
│  3. DATA POINT VALIDATION                                                    │
│     For each data point defined in section:                                  │
│       → Extract from all configured sources                                  │
│       → Cross-validate (exact match, fuzzy match, numeric tolerance)         │
│       → Flag conflicts for reviewer                                          │
│       → Determine canonical value                                            │
│                                                                              │
│  4. SECTION GENERATION                                                       │
│     For each section in template:                                            │
│       Prompt = instructions + validated data points + source context         │
│       → Claude generates section content                                     │
│       → Track citations per data point                                       │
│                                                                              │
│  5. DOCUMENT ASSEMBLY                                                        │
│     → Combine sections                                                       │
│     → Apply document template (headers, footers, styles)                     │
│     → Convert to output format (DOCX/PDF)                                    │
│                                                                              │
│  6. REVIEW TASK                                                              │
│     → Side-by-side: Generated doc | Data points with sources                 │
│     → Reviewer resolves conflicts                                            │
│     → Can regenerate individual sections                                     │
│     → Approve final document                                                 │
│                                                                              │
│  7. FINALIZE                                                                 │
│     → Store in DMS                                                           │
│     → Webhook to configured endpoints                                        │
│     → Audit trail saved                                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Point Validation

Data points are factual assertions that must be validated across multiple sources:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DATA POINT VALIDATION FLOW                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. EXTRACT DATA POINTS FROM EACH SOURCE                                     │
│     For data_point "employee_count":                                         │
│       Source: company_profile (API) → 5,200                                  │
│       Source: financials (PDF) → 5,150                                       │
│       Source: presentation (PPTX) → 5,500                                    │
│                                                                              │
│  2. CROSS-VALIDATE ACROSS SOURCES                                            │
│     validation_type: numeric_tolerance (5%)                                  │
│       5,200 vs 5,150 → MATCH (within 5%)                                     │
│       5,200 vs 5,500 → CONFLICT (5.8% difference)                            │
│     Result: CONFLICT - flagged for reviewer                                  │
│                                                                              │
│  3. GENERATE WITH VALIDATED DATA POINTS                                      │
│     Prompt includes validated values + conflict flags                        │
│                                                                              │
│  4. TRACK CITATIONS PER DATA POINT                                           │
│     Generated text links to source documents/pages                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Maker-Checker Workflow

### Extraction Review UI

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  EXTRACTION REVIEW: Deal LOAN-2024-001 | Pipeline: covenant-compliance       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────┬────────────────────────────────────┐    │
│  │  PDF VIEWER                    │  EXTRACTED FIELDS                   │    │
│  │                                │                                     │    │
│  │  [compliance_cert.pdf]         │  covenant_period:                   │    │
│  │                                │    start_date: 2024-01-01 ✓        │    │
│  │  ┌──────────────────────────┐  │    end_date: 2024-03-31 ✓          │    │
│  │  │                          │  │    confidence: 0.98                 │    │
│  │  │  Page 2                  │  │    [View Citation]                  │    │
│  │  │                          │  │                                     │    │
│  │  │  ┌────────────────────┐  │  │  leverage_ratio:                    │    │
│  │  │  │ HIGHLIGHTED TEXT   │  │  │    value: 3.2 ⚠ (low confidence)   │    │
│  │  │  │ "Debt/EBITDA: 3.2" │  │  │    confidence: 0.72                 │    │
│  │  │  └────────────────────┘  │  │    [View Citation] [Override]       │    │
│  │  │                          │  │                                     │    │
│  │  └──────────────────────────┘  │  compliance_status:                 │    │
│  │                                │    value: COMPLIANT ✓               │    │
│  │  [◄ Prev] [Page 2 of 15] [►]   │    confidence: 0.95                 │    │
│  │                                │                                     │    │
│  └────────────────────────────────┴────────────────────────────────────┘    │
│                                                                              │
│  ATTESTATION                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Reviewer: analyst@company.com                                       │    │
│  │  Status: 4/5 fields attested                                         │    │
│  │                                                                      │    │
│  │  [Attest All Remaining]  [Submit for Approval]                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Revision History

```
Revision History View:
┌────────────────────────────────────────────────────────────────┐
│  Deal: LOAN-2024-001  │  Field: leverage_ratio                 │
├────────────────────────────────────────────────────────────────┤
│  v1  │  3.2   │  AI extracted  │  2024-01-15  │  APPROVED      │
│  v2  │  3.5   │  AI extracted  │  2024-01-20  │  OVERRIDDEN    │
│      │  3.4   │  Manual        │  2024-01-20  │  By: manager   │
│      │        │                │              │  "Corrected..."│
└────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Reasoning |
|-------|------------|-----------|
| **Backend** | Python + FastAPI | Best document processing ecosystem, strong AI/LLM libraries, Pydantic for validation |
| **Workflow** | Temporal | Durable workflows, retries, state management, visibility |
| **Queue** | Apache Kafka | High throughput, event replay, exactly-once semantics |
| **Database** | PostgreSQL | ACID transactions, JSONB for flexible schemas |
| **Document Store** | S3 | Scalable blob storage |
| **Cache** | Redis | Real-time state, caching |
| **AI/Extraction** | Claude API | Vision for OCR docs, structured extraction |
| **Frontend** | React + TypeScript | Checker review UI |
| **Infrastructure** | AWS (EKS, RDS, S3, MSK) | Production environment |

---

## Configuration

Pipelines are configured via YAML files committed to the repository. See `config/pipelines/` for examples.

### Extraction Pipeline Configuration

```yaml
extraction_use_case:
  id: "covenant-compliance"
  name: "Covenant Compliance Extraction"

  document_types:
    - type: compliance_certificate
      required: true
    - type: financial_statement
      required: true

  triggers:
    manual:
      enabled: true
      roles: [loan_ops, analyst]
    rules:
      - name: "Auto-trigger when docs present"
        when:
          type: document_set_complete
          document_types: [compliance_certificate, financial_statement]

  extraction_schema:
    covenant_period:
      type: object
      properties:
        start_date: { type: date }
        end_date: { type: date }
      likely_sections: ["Definitions", "Financial Covenants"]

  workflow:
    maker_checker:
      enabled: true
      multi_attest:
        required_count: 2

  post_sinks:
    - type: webhook
      url: "https://core-banking/api/covenants"
```

### Generation Pipeline Configuration

```yaml
generation_pipeline:
  id: "credit-memo-generator"
  name: "Credit Memo Generator"

  output:
    format: docx
    store_in_dms: true

  data_sources:
    deal_info:
      type: api
      endpoint: "https://core-banking/api/deals/{deal_id}"
    financials:
      type: dms
      document_types: ["financial_statement"]

  template:
    sections:
      - id: executive_summary
        name: "Executive Summary"
        instructions: "Write a 2-3 paragraph summary..."
        data_sources: [deal_info]
        data_points:
          - id: borrower_name
            sources: [deal_info, financials]
            validation: fuzzy_match
```

---

## API Endpoints

### Extraction

- `POST /api/v1/extractions` - Trigger extraction
- `GET /api/v1/extractions/{id}` - Get extraction run
- `GET /api/v1/deals/{deal_id}/extractions` - List extractions for deal

### Generation

- `POST /api/v1/generations` - Trigger generation
- `GET /api/v1/generations/{id}` - Get generation run
- `POST /api/v1/generations/{id}/sections/{section_id}/regenerate` - Regenerate section

### Review

- `GET /api/v1/reviews` - List review tasks
- `GET /api/v1/reviews/{id}` - Get review task
- `POST /api/v1/reviews/{id}/attest` - Submit attestation
- `POST /api/v1/reviews/{id}/override` - Override field value

---

## Local Development

```bash
# Start local infrastructure
docker-compose up -d

# Run API server
uvicorn src.api.app:app --reload

# Run worker
python -m src.workers.extraction_worker
```

See `docker-compose.yaml` for local service configuration.
