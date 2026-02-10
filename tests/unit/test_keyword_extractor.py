from src.core.models import DocumentNode, DocumentStructure, KeywordEntry, PageLayout
from src.indexing.keyword_extractor import KeywordExtractor


class FakeLLM:
    async def query_json(self, prompt: str, max_tokens: int = 2000) -> dict:
        return {"mappings": {"leverage ratio": "total leverage ratio"}}


def _sample_structure() -> DocumentStructure:
    return DocumentStructure(
        document_id="doc-1",
        root=DocumentNode(
            id="root",
            title="root",
            level=0,
            children=[
                DocumentNode(
                    id="n1",
                    title="Definitions",
                    level=1,
                    start_page=1,
                    end_page=2,
                )
            ],
        ),
        total_pages=2,
    )


async def test_keyword_extractor_regex_candidates():
    extractor = KeywordExtractor(max_keywords=50)
    layouts = [
        PageLayout(
            page_number=1,
            headers=["Section 1.01 Definitions"],
            paragraphs=[
                '"Leverage Ratio" means the ratio of Total Debt to EBITDA.',
                "Section 2.01 references Interest Coverage Ratio.",
            ],
        )
    ]

    keywords = await extractor.extract_keywords(layouts, _sample_structure())
    by_term = {k.canonical_term: k for k in keywords}

    assert "leverage ratio" in by_term
    assert "ebitda" in by_term
    assert by_term["leverage ratio"].definition_page == 1


async def test_keyword_extractor_llm_normalization():
    extractor = KeywordExtractor(llm_client=FakeLLM(), max_keywords=50)
    layouts = [
        PageLayout(
            page_number=1,
            paragraphs=['"Leverage Ratio" shall be tested quarterly.'],
        )
    ]

    keywords = await extractor.extract_keywords(layouts, use_llm=True)
    assert isinstance(keywords, list)
    assert any(isinstance(k, KeywordEntry) for k in keywords)
