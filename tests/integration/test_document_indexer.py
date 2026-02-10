from src.core.models import DocumentNode, DocumentStructure, KeywordEntry, PageLayout
from src.indexing.document_indexer import DocumentIndexer


class FakeLayoutAnalyzer:
    def analyze_document(self, pdf_path):
        return [
            PageLayout(
                page_number=1,
                headers=["Definitions"],
                paragraphs=['"Leverage Ratio" means ...'],
            )
        ]


class FakeStructureExtractor:
    async def extract(self, pdf_path: str):
        return DocumentStructure(
            document_id="",
            root=DocumentNode(
                id="root",
                title="root",
                level=0,
                children=[DocumentNode(id="n1", title="Definitions", level=1, start_page=1)],
            ),
            total_pages=1,
        )


class FakeKeywordExtractor:
    async def extract_keywords(self, page_layouts, structure, use_llm=False):
        return [KeywordEntry(term="Leverage Ratio", canonical_term="leverage ratio", pages=[1])]


async def test_document_indexer_builds_complete_index(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%fake")

    indexer = DocumentIndexer(
        layout_analyzer=FakeLayoutAnalyzer(),
        structure_extractor=FakeStructureExtractor(),
        keyword_extractor=FakeKeywordExtractor(),
    )

    result = await indexer.build_index(
        pdf_path=pdf_path,
        document_id="doc-1",
        document_type="credit_agreement",
    )

    assert result.document_id == "doc-1"
    assert result.document_type == "credit_agreement"
    assert result.total_pages == 1
    assert result.structure is not None
    assert result.keyword_index[0].canonical_term == "leverage ratio"
