from src.core.models import (
    CrossDocumentReference,
    DealPageIndex,
    DocumentNode,
    DocumentPageIndex,
    DocumentStructure,
    KeywordEntry,
    PageLayout,
    TermType,
)
from src.tools.index_tools import IndexTools


def _build_deal_index() -> DealPageIndex:
    structure = DocumentStructure(
        document_id="doc-1",
        root=DocumentNode(
            id="root",
            title="root",
            level=0,
            children=[
                DocumentNode(
                    id="node-def",
                    title="Definitions",
                    level=1,
                    start_page=1,
                    end_page=2,
                ),
                DocumentNode(
                    id="node-cov",
                    title="Financial Covenants",
                    level=1,
                    start_page=3,
                    end_page=5,
                ),
            ],
        ),
        total_pages=5,
    )
    doc_index = DocumentPageIndex(
        document_id="doc-1",
        document_type="credit_agreement",
        total_pages=5,
        structure=structure,
        page_layouts=[
            PageLayout(page_number=1, paragraphs=['"Leverage Ratio" definition']),
            PageLayout(page_number=3, headers=["Financial Covenants"], paragraphs=["EBITDA covenant text"]),
        ],
        keyword_index=[
            KeywordEntry(
                term="Leverage Ratio",
                canonical_term="leverage ratio",
                pages=[1, 3],
                sections=["Definitions", "Financial Covenants"],
                term_type=TermType.FINANCIAL_METRIC,
                definition_page=1,
            ),
            KeywordEntry(
                term="EBITDA",
                canonical_term="ebitda",
                pages=[3],
                sections=["Financial Covenants"],
                term_type=TermType.FINANCIAL_METRIC,
            ),
        ],
    )
    return DealPageIndex(
        deal_id="deal-1",
        document_registry={"doc-1": "credit_agreement"},
        document_indexes={"doc-1": doc_index},
        unified_keywords=list(doc_index.keyword_index),
        cross_references=[
            CrossDocumentReference(
                source_document_id="doc-1",
                source_page=3,
                reference_text="as defined in Section 1.01",
                target_document_id="doc-1",
                target_node_id="node-def",
                target_page=1,
                confidence=0.9,
            )
        ],
    )


def test_index_tools_core_methods():
    tools = IndexTools(_build_deal_index())

    assert tools.find_section("covenant")
    assert tools.lookup_keyword("ebitda")
    assert tools.find_term_across_docs("leverage ratio")

    definition = tools.get_definition("Leverage Ratio")
    assert definition is not None
    assert definition["page"] == 1

    subtree = tools.get_subtree("node-cov")
    assert subtree is not None
    assert subtree["node_id"] == "node-cov"

    pages = tools.get_page_content("doc-1", [3])
    assert len(pages) == 1

    hits = tools.search_in_section("node-cov", "EBITDA")
    assert hits

    refs = tools.resolve_reference("doc-1", 3)
    assert refs and refs[0]["target_node_id"] == "node-def"

    amendments = tools.get_amendments_for_section("node-def")
    assert amendments and amendments[0]["source_page"] == 3

    summary = tools.get_index_summary()
    assert summary["deal_id"] == "deal-1"


def test_find_section_falls_back_to_keyword_and_page_content():
    deal = _build_deal_index()
    # Remove title signal to force fallback path.
    deal.document_indexes["doc-1"].structure.root.children[1].title = "Section 5.03"
    deal.document_indexes["doc-1"].keyword_index[1].sections = ["Section 5.03"]
    deal.unified_keywords = list(deal.document_indexes["doc-1"].keyword_index)

    tools = IndexTools(deal)
    results = tools.find_section("covenant")
    assert results
    assert any(r["title"] == "Section 5.03" for r in results)
