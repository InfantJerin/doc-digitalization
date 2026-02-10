from src.core.models import DocumentPageIndex, PageLayout
from src.indexing.cross_reference_detector import CrossReferenceDetector


class FakeLLM:
    async def query_json(self, prompt: str, max_tokens: int = 2000) -> dict:
        return {
            "resolved": [
                {
                    "candidate_index": 0,
                    "target_doc_id": "doc-credit",
                    "target_node_id": "node-1",
                    "target_page": 10,
                    "confidence": 0.92,
                }
            ]
        }


async def test_cross_reference_detector_heuristic_resolution():
    detector = CrossReferenceDetector()
    source = DocumentPageIndex(
        document_id="doc-cert",
        document_type="compliance_certificate",
        page_layouts=[
            PageLayout(
                page_number=2,
                paragraphs=[
                    "Consolidated EBITDA is as defined in Section 1.01 of the Credit Agreement."
                ],
            )
        ],
    )
    all_indexes = {
        "doc-cert": source,
        "doc-credit": DocumentPageIndex(
            document_id="doc-credit",
            document_type="credit_agreement",
        ),
    }

    refs = await detector.detect_cross_references("doc-cert", source, all_indexes)
    assert len(refs) == 1
    assert refs[0].target_document_id == "doc-credit"


async def test_cross_reference_detector_llm_resolution():
    detector = CrossReferenceDetector(llm_client=FakeLLM())
    source = DocumentPageIndex(
        document_id="doc-cert",
        page_layouts=[
            PageLayout(
                page_number=3,
                paragraphs=["as defined in Section 1.01 of the Credit Agreement"],
            )
        ],
    )
    all_indexes = {
        "doc-cert": source,
        "doc-credit": DocumentPageIndex(
            document_id="doc-credit",
            document_type="credit_agreement",
        ),
    }

    refs = await detector.detect_cross_references("doc-cert", source, all_indexes)
    assert len(refs) == 1
    assert refs[0].target_node_id == "node-1"
    assert refs[0].target_page == 10
