import pytest

from src.core.models import (
    AttestationDecision,
    ExtractedField,
    ExtractionRun,
    PipelineType,
    RunStatus,
)
from src.database.repositories.extraction_repo import ExtractionRepository
from src.database.repositories.review_repo import ReviewRepository
from src.workflow.service import WorkflowService


@pytest.mark.asyncio
async def test_workflow_attestation_override_updates_run():
    extraction_repo = ExtractionRepository()
    review_repo = ReviewRepository()

    run = ExtractionRun(
        id="run-1",
        deal_id="deal-1",
        pipeline_id="credit-agreement",
        status=RunStatus.AWAITING_REVIEW,
        extracted_fields=[ExtractedField(field_path="borrower", value={"legal_name": "Old Name"}, confidence=0.7)],
    )
    await extraction_repo.create_run(run)

    service = WorkflowService(review_repo=review_repo, extraction_repo=extraction_repo)
    task = await service.create_review_task(
        run_id=run.id,
        run_type=PipelineType.EXTRACTION,
        required_attestations=1,
        assignees=["analyst"],
    )

    await service.submit_attestation(
        task_id=task.id,
        reviewer_id="u-1",
        reviewer_email="a@example.com",
        decision=AttestationDecision.OVERRIDE,
        fields_attested=["borrower"],
        overrides=[
            {
                "field_path": "borrower",
                "original_value": {"legal_name": "Old Name"},
                "new_value": {"legal_name": "New Name"},
                "justification": "Source clause clearly names New Name as Borrower.",
            }
        ],
    )

    updated = await extraction_repo.get_run(run.id)
    assert updated is not None
    field = updated.get_field("borrower")
    assert field is not None
    assert field.overridden is True
    assert field.override_value == {"legal_name": "New Name"}
