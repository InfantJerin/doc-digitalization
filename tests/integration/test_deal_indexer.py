from src.core.models import CrossDocumentReference, DocumentPageIndex, KeywordEntry
from src.indexing.deal_indexer import DealIndexer


class FakeCrossReferenceDetector:
    async def detect_cross_references(self, source_doc_id, source_index, all_indexes):
        if source_doc_id == "doc-2":
            return [
                CrossDocumentReference(
                    source_document_id="doc-2",
                    source_page=3,
                    reference_text="as defined in the Credit Agreement",
                    target_document_id="doc-1",
                    target_node_id="",
                    target_page=10,
                    confidence=0.8,
                )
            ]
        return []


async def test_deal_indexer_builds_unified_index():
    doc_1 = DocumentPageIndex(
        document_id="doc-1",
        document_type="credit_agreement",
        keyword_index=[KeywordEntry(term="EBITDA", canonical_term="ebitda", pages=[4])],
    )
    doc_2 = DocumentPageIndex(
        document_id="doc-2",
        document_type="compliance_certificate",
        keyword_index=[KeywordEntry(term="EBITDA", canonical_term="ebitda", pages=[2])],
    )

    indexer = DealIndexer(cross_reference_detector=FakeCrossReferenceDetector())
    result = await indexer.build_deal_index(
        deal_id="deal-1",
        document_indexes={"doc-1": doc_1, "doc-2": doc_2},
        detect_cross_references=True,
    )

    assert result.deal_id == "deal-1"
    assert result.document_registry["doc-1"] == "credit_agreement"
    assert result.unified_keywords
    assert result.unified_keywords[0].canonical_term == "ebitda"
    assert result.cross_references
