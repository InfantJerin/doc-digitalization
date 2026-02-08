from src.core.schemas import ExtractedFieldOutput, ExtractionResultOutput


def test_extraction_result_schema_defaults():
    payload = ExtractionResultOutput()

    assert payload.fields == []
    assert payload.extraction_notes == []
    assert payload.agent_session_id is None


def test_extracted_field_schema_accepts_nested_values():
    field = ExtractedFieldOutput(
        field_path="total_commitment",
        value={"amount": 1000000, "currency": "USD"},
        confidence=0.91,
    )

    assert field.field_path == "total_commitment"
    assert field.value["currency"] == "USD"
