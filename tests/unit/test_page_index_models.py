from src.core.models import (
    CrossDocumentReference,
    DealPageIndex,
    DocumentNode,
    DocumentPageIndex,
    DocumentStructure,
    ExtractionMode,
    KeywordEntry,
    PageLayout,
    TermType,
)


def test_page_layout_roundtrip():
    layout = PageLayout(
        page_number=4,
        headers=["Section 1.01"],
        paragraphs=["Some paragraph text."],
        tables=[{"rows": 2, "columns": 2, "data": [["a", "b"], ["c", "d"]]}],
        footnotes=["1 Some footnote"],
        images=[{"bbox": [0, 0, 10, 10]}],
        word_count=42,
    )
    restored = PageLayout.from_dict(layout.to_dict())
    assert restored == layout


def test_keyword_entry_roundtrip():
    entry = KeywordEntry(
        term="EBITDA",
        canonical_term="ebitda",
        pages=[2, 4],
        sections=["Definitions"],
        term_type=TermType.FINANCIAL_METRIC,
        definition_page=2,
    )
    restored = KeywordEntry.from_dict(entry.to_dict())
    assert restored == entry


def test_cross_document_reference_roundtrip():
    ref = CrossDocumentReference(
        source_document_id="doc-2",
        source_page=3,
        reference_text="as defined in Section 1.01 of the Credit Agreement",
        target_document_id="doc-1",
        target_node_id="node-5",
        target_page=28,
        confidence=0.9,
    )
    restored = CrossDocumentReference.from_dict(ref.to_dict())
    assert restored == ref


def test_document_page_index_roundtrip():
    structure = DocumentStructure(
        document_id="doc-1",
        root=DocumentNode(
            id="root",
            title="root",
            level=0,
            start_page=1,
            children=[
                DocumentNode(
                    id="node-1",
                    title="Definitions",
                    level=1,
                    start_page=2,
                    end_page=5,
                )
            ],
        ),
        mode_used=ExtractionMode.TOC_WITH_PAGES,
        total_pages=12,
        toc_pages=[1],
    )
    index = DocumentPageIndex(
        document_id="doc-1",
        document_type="credit_agreement",
        total_pages=12,
        structure=structure,
        page_layouts=[PageLayout(page_number=1)],
        keyword_index=[KeywordEntry(term="EBITDA", canonical_term="ebitda", pages=[3])],
    )
    restored = DocumentPageIndex.from_dict(index.to_dict())
    assert restored.document_id == index.document_id
    assert restored.document_type == index.document_type
    assert restored.total_pages == 12
    assert restored.structure is not None
    assert restored.structure.mode_used == ExtractionMode.TOC_WITH_PAGES
    assert restored.keyword_index[0].canonical_term == "ebitda"


def test_deal_page_index_roundtrip():
    doc_index = DocumentPageIndex(document_id="doc-1", document_type="credit_agreement")
    deal = DealPageIndex(
        deal_id="deal-1",
        document_registry={"doc-1": "credit_agreement"},
        document_indexes={"doc-1": doc_index},
        unified_keywords=[KeywordEntry(term="EBITDA", canonical_term="ebitda", pages=[3])],
        cross_references=[
            CrossDocumentReference(
                source_document_id="doc-2",
                source_page=3,
                reference_text="as defined in Credit Agreement",
                target_document_id="doc-1",
                target_node_id="",
                target_page=28,
                confidence=0.7,
            )
        ],
    )
    restored = DealPageIndex.from_dict(deal.to_dict())
    assert restored.deal_id == "deal-1"
    assert "doc-1" in restored.document_indexes
    assert restored.unified_keywords[0].canonical_term == "ebitda"
    assert restored.cross_references[0].target_document_id == "doc-1"
