from src.core.models import DealPageIndex, DocumentPageIndex, KeywordEntry
from src.indexing.index_store import IndexStore


def test_index_store_save_and_load_document_index(tmp_path):
    store = IndexStore(tmp_path)
    doc_index = DocumentPageIndex(
        document_id="doc-1",
        document_type="credit_agreement",
        total_pages=10,
        keyword_index=[KeywordEntry(term="EBITDA", canonical_term="ebitda", pages=[2])],
    )

    path = store.save_document_index(doc_index)
    loaded = store.load_document_index("doc-1")

    assert path.exists()
    assert loaded.document_id == "doc-1"
    assert loaded.keyword_index[0].canonical_term == "ebitda"
    assert store.has_document_index("doc-1")
    assert "doc-1" in store.list_document_indexes()


def test_index_store_save_and_load_deal_index(tmp_path):
    store = IndexStore(tmp_path)
    deal_index = DealPageIndex(
        deal_id="deal-1",
        document_registry={"doc-1": "credit_agreement"},
        document_indexes={"doc-1": DocumentPageIndex(document_id="doc-1")},
        unified_keywords=[KeywordEntry(term="EBITDA", canonical_term="ebitda", pages=[2])],
    )

    path = store.save_deal_index(deal_index)
    loaded = store.load_deal_index()

    assert path.exists()
    assert loaded.deal_id == "deal-1"
    assert loaded.unified_keywords[0].term == "EBITDA"
