from src.agent.result_parser import ResultParser
from src.core.schemas import CitationOutput, ExtractedFieldOutput, ExtractionResultOutput


def test_result_parser_maps_structured_output_to_domain_fields():
    parser = ResultParser()

    payload = ExtractionResultOutput(
        fields=[
            ExtractedFieldOutput(
                field_path="borrower",
                value={"legal_name": "Acme LLC"},
                confidence=0.88,
                citation=CitationOutput(
                    document_id="doc-1",
                    page_number=3,
                    extracted_text="Borrower means Acme LLC",
                    confidence=0.88,
                    bounding_box={"x": 1.0, "y": 2.0, "width": 3.0, "height": 4.0},
                ),
            )
        ]
    )

    fields = parser.parse_fields(payload)

    assert len(fields) == 1
    assert fields[0].field_path == "borrower"
    assert fields[0].citation is not None
    assert fields[0].citation.page_number == 3
