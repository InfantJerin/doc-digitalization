# Next Steps - Document Digitalization Platform

This document outlines the remaining work to make the platform production-ready.

---

## 1. Temporal Workflow Integration

**Priority: High**

The current implementation uses direct service calls. Temporal should be added for durable, observable workflows.

### 1.1 Add Temporal Dependencies

```bash
pip install temporalio
```

### 1.2 Create Workflow Definitions

```
src/workflows/
├── __init__.py
├── extraction_workflow.py    # ExtractionWorkflow
├── generation_workflow.py    # GenerationWorkflow
├── review_workflow.py        # ReviewWorkflow (signal-based wait)
└── activities/
    ├── document_activities.py
    ├── extraction_activities.py
    ├── generation_activities.py
    └── review_activities.py
```

### 1.3 Extraction Workflow Steps

```python
@workflow.defn
class ExtractionWorkflow:
    @workflow.run
    async def run(self, request: ExtractionRequest) -> ExtractionResult:
        # 1. Fetch documents from DMS
        documents = await workflow.execute_activity(
            fetch_documents,
            args=[request.document_ids],
            start_to_close_timeout=timedelta(minutes=5)
        )

        # 2. Extract structure (for large docs)
        structures = await workflow.execute_activity(
            extract_structures,
            args=[documents],
            start_to_close_timeout=timedelta(minutes=10)
        )

        # 3. Extract fields with citations
        extracted_fields = await workflow.execute_activity(
            extract_fields,
            args=[documents, structures, request.schema],
            start_to_close_timeout=timedelta(minutes=15)
        )

        # 4. Create review task
        review_task = await workflow.execute_activity(
            create_review_task,
            args=[extracted_fields],
            start_to_close_timeout=timedelta(minutes=1)
        )

        # 5. Wait for human attestation (signal)
        await workflow.wait_condition(lambda: self.attestation_complete)

        # 6. Deliver to post-sink
        await workflow.execute_activity(
            deliver_to_post_sink,
            args=[extracted_fields, request.post_sinks],
            start_to_close_timeout=timedelta(minutes=5)
        )

        return ExtractionResult(...)

    @workflow.signal
    def complete_attestation(self, attestation: Attestation):
        self.attestation_complete = True
        self.attestation = attestation
```

### 1.4 Generation Workflow Steps

```python
@workflow.defn
class GenerationWorkflow:
    @workflow.run
    async def run(self, request: GenerationRequest) -> GenerationResult:
        # 1. Gather data from all sources
        data_context = await workflow.execute_activity(
            gather_data,
            args=[request.deal_id, request.data_sources],
            start_to_close_timeout=timedelta(minutes=10)
        )

        # 2. Validate data points
        validated_data = await workflow.execute_activity(
            validate_data_points,
            args=[data_context, request.template],
            start_to_close_timeout=timedelta(minutes=5)
        )

        # 3. Generate sections (can be parallel)
        sections = await workflow.execute_activity(
            generate_sections,
            args=[validated_data, request.template],
            start_to_close_timeout=timedelta(minutes=20)
        )

        # 4. Assemble document
        document = await workflow.execute_activity(
            assemble_document,
            args=[sections, request.output_config],
            start_to_close_timeout=timedelta(minutes=5)
        )

        # 5. Create review task and wait
        await workflow.execute_activity(create_review_task, ...)
        await workflow.wait_condition(lambda: self.review_complete)

        # 6. Store final document and deliver
        await workflow.execute_activity(finalize_and_deliver, ...)

        return GenerationResult(...)
```

### 1.5 Temporal Worker

```python
# src/workers/temporal_worker.py
async def main():
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue="doc-digitalization",
        workflows=[ExtractionWorkflow, GenerationWorkflow, ReviewWorkflow],
        activities=[
            fetch_documents,
            extract_structures,
            extract_fields,
            gather_data,
            validate_data_points,
            generate_sections,
            assemble_document,
            create_review_task,
            deliver_to_post_sink,
        ]
    )

    await worker.run()
```

### 1.6 Infrastructure

- Add Temporal server to `docker-compose.yaml`
- Configure Temporal namespace
- Set up Temporal Web UI for visibility

---

## 2. Database Integration

**Priority: High**

### 2.1 Add SQLAlchemy Models

```
src/database/
├── __init__.py
├── connection.py
├── models/
│   ├── deal.py
│   ├── document.py
│   ├── extraction_run.py
│   ├── generation_run.py
│   ├── review_task.py
│   ├── attestation.py
│   └── revision.py
└── repositories/
    ├── deal_repository.py
    ├── extraction_repository.py
    └── review_repository.py
```

### 2.2 Database Migrations

```bash
pip install alembic
alembic init migrations
```

### 2.3 Key Tables

| Table | Purpose |
|-------|---------|
| `deals` | Deal/loan information |
| `documents` | Document metadata |
| `document_structures` | Cached structure trees |
| `extraction_runs` | Extraction run records |
| `extracted_fields` | Field values with citations |
| `generation_runs` | Generation run records |
| `generated_sections` | Section content with data points |
| `review_tasks` | Review task assignments |
| `attestations` | Attestation records |
| `field_revisions` | Revision history |
| `webhook_deliveries` | Audit of webhook deliveries |

---

## 3. Checker UI (React Frontend)

**Priority: High**

### 3.1 Project Setup

```bash
cd ui/checker-app
npx create-react-app . --template typescript
npm install @react-pdf-viewer/core @react-pdf-viewer/default-layout
npm install axios react-query tailwindcss
```

### 3.2 Key Components

```
ui/checker-app/src/
├── components/
│   ├── PdfViewer/
│   │   ├── PdfViewer.tsx
│   │   ├── PageRenderer.tsx
│   │   └── CitationHighlight.tsx
│   ├── FieldList/
│   │   ├── FieldList.tsx
│   │   ├── FieldCard.tsx
│   │   └── ConfidenceBadge.tsx
│   ├── DataPointPanel/
│   │   ├── DataPointPanel.tsx
│   │   ├── SourceComparison.tsx
│   │   └── ConflictResolver.tsx
│   ├── AttestationForm/
│   │   ├── AttestationForm.tsx
│   │   └── OverrideModal.tsx
│   └── RevisionHistory/
│       └── RevisionTimeline.tsx
├── pages/
│   ├── ExtractionReview.tsx
│   ├── GenerationReview.tsx
│   └── ReviewList.tsx
└── api/
    └── reviewApi.ts
```

### 3.3 Key Features

- **Split View**: PDF on left, extracted fields on right
- **Citation Highlighting**: Click field → highlight in PDF with bounding box
- **Confidence Indicators**: Color-coded confidence scores
- **Data Point Conflicts**: Show source values, allow resolution
- **Inline Override**: Edit value with justification modal
- **Revision History**: Timeline view of changes
- **Multi-Attest**: Track attestation progress

### 3.4 Wireframe Reference

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  EXTRACTION REVIEW: Deal LOAN-2024-001                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────┬────────────────────────────────────┐    │
│  │  PDF VIEWER                    │  EXTRACTED FIELDS                   │    │
│  │                                │                                     │    │
│  │  [Document selector dropdown]  │  ☑ covenant_period                  │    │
│  │                                │    start: 2024-01-01 ✓ (0.98)       │    │
│  │  ┌──────────────────────────┐  │    end: 2024-03-31 ✓ (0.98)         │    │
│  │  │                          │  │    [View Citation]                  │    │
│  │  │  Page content with       │  │                                     │    │
│  │  │  highlighted citation    │  │  ☐ leverage_ratio                   │    │
│  │  │  ┌────────────────────┐  │  │    value: 3.2 ⚠ (0.72)              │    │
│  │  │  │ HIGHLIGHTED TEXT   │  │  │    [View Citation] [Override]       │    │
│  │  │  └────────────────────┘  │  │                                     │    │
│  │  │                          │  │  ☑ compliance_status                │    │
│  │  └──────────────────────────┘  │    value: COMPLIANT ✓ (0.95)        │    │
│  │                                │                                     │    │
│  │  [◄ Prev] Page 2/15 [Next ►]   │  ─────────────────────────────      │    │
│  │                                │  Attestation: 2/3 fields            │    │
│  │                                │  [Attest Selected] [Submit All]     │    │
│  └────────────────────────────────┴────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Authentication & Authorization

**Priority: Medium**

### 4.1 Add OAuth2/JWT

```bash
pip install python-jose[cryptography] passlib[bcrypt]
```

### 4.2 Role-Based Access

| Role | Permissions |
|------|-------------|
| `developer` | Configure pipelines, view all |
| `loan_ops` | Trigger extractions, view deals |
| `analyst` | Review, attest fields |
| `senior_analyst` | Review, attest, override |
| `admin` | All permissions |

### 4.3 Integration Points

- FastAPI security dependencies
- Temporal workflow authorization
- UI authentication flow

---

## 5. Message Queue Integration

**Priority: Medium**

### 5.1 Kafka Setup

```yaml
# docker-compose.yaml additions
kafka:
  image: confluentinc/cp-kafka:latest
  environment:
    KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
    KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092

zookeeper:
  image: confluentinc/cp-zookeeper:latest
```

### 5.2 Topics

| Topic | Purpose |
|-------|---------|
| `doc-received` | New document uploaded |
| `extraction-requested` | Extraction trigger event |
| `extraction-completed` | Extraction finished |
| `generation-requested` | Generation trigger event |
| `generation-completed` | Generation finished |
| `review-completed` | Attestation submitted |

### 5.3 Event Consumers

- Connect Kafka consumers to Temporal workflow starters
- Dead letter queue for failed events

---

## 6. Observability

**Priority: Medium**

### 6.1 Structured Logging

```python
import structlog

logger = structlog.get_logger()
logger.info(
    "extraction_started",
    deal_id=deal_id,
    pipeline_id=pipeline_id,
    document_count=len(document_ids)
)
```

### 6.2 Metrics (Prometheus)

```python
from prometheus_client import Counter, Histogram

extraction_counter = Counter(
    'extractions_total',
    'Total extractions',
    ['pipeline_id', 'status']
)

extraction_duration = Histogram(
    'extraction_duration_seconds',
    'Extraction duration',
    ['pipeline_id']
)
```

### 6.3 Dashboards

- Grafana dashboard for extraction/generation metrics
- Temporal Web UI for workflow visibility
- Custom Loan Ops dashboard for deal pipeline view

---

## 7. Testing

**Priority: Medium**

### 7.1 Unit Tests

- [ ] Structure extractor tests (all 4 strategies)
- [ ] Field extractor tests
- [ ] Data point validator tests (all validation types)
- [ ] Section generator tests
- [ ] Document assembler tests

### 7.2 Integration Tests

- [ ] End-to-end extraction flow
- [ ] End-to-end generation flow
- [ ] Review workflow with attestation
- [ ] Webhook delivery

### 7.3 Test Data

- Sample PDFs for extraction testing
- Mock DMS responses
- Sample API responses for generation

---

## 8. Infrastructure (AWS)

**Priority: Low (for initial deployment)**

### 8.1 Terraform Resources

```
infrastructure/terraform/aws/
├── main.tf
├── variables.tf
├── outputs.tf
├── modules/
│   ├── eks/           # Kubernetes cluster
│   ├── rds/           # PostgreSQL
│   ├── msk/           # Kafka
│   ├── elasticache/   # Redis
│   └── s3/            # Document storage
```

### 8.2 Kubernetes Manifests

```
infrastructure/k8s/prod/
├── namespace.yaml
├── api-deployment.yaml
├── temporal-worker-deployment.yaml
├── extraction-worker-deployment.yaml
├── generation-worker-deployment.yaml
├── configmaps.yaml
├── secrets.yaml
└── ingress.yaml
```

---

## 9. Documentation

**Priority: Low**

- [ ] API documentation (OpenAPI/Swagger) - Auto-generated
- [ ] Pipeline configuration guide
- [ ] Deployment guide
- [ ] Runbook for operations
- [ ] Architecture decision records (ADRs)

---

## Implementation Order

### Phase 1: Core Functionality (Weeks 1-2)
1. Database integration
2. Temporal workflow integration
3. Complete API endpoints

### Phase 2: UI & Review (Weeks 3-4)
4. Checker UI development
5. Authentication integration
6. End-to-end testing

### Phase 3: Production Readiness (Weeks 5-6)
7. Kafka integration
8. Observability (logging, metrics)
9. AWS infrastructure
10. Security hardening

---

## Open Questions

1. **DMS Integration**: What is the actual DMS API contract? Need OpenAPI spec or documentation.

2. **Authentication Provider**: Which IdP will be used? (Okta, Auth0, Azure AD, etc.)

3. **Notification Requirements**: Should reviewers be notified via email/Slack when tasks are assigned?

4. **Retention Policy**: How long should extraction/generation results be retained?

5. **Multi-tenancy**: Is this single-tenant or multi-tenant? Affects data isolation approach.

6. **Disaster Recovery**: RTO/RPO requirements for the platform?
