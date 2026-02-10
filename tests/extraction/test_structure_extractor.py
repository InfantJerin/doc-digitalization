"""
Tests for Document Structure Extractor.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from src.extraction.structure_extractor import (
    DocumentStructureExtractor,
    StructureExtractionConfig,
)
from src.core.models import DocumentNode, ExtractionMode


class TestDocumentStructureExtractor:
    """Tests for DocumentStructureExtractor."""

    @pytest.fixture
    def mock_claude_client(self):
        """Create a mock Claude client."""
        client = Mock()
        client.query_json = AsyncMock()
        return client

    @pytest.fixture
    def extractor(self, mock_claude_client):
        """Create an extractor with mocked dependencies."""
        return DocumentStructureExtractor(
            claude_client=mock_claude_client,
            config=StructureExtractionConfig(
                toc_check_pages=10,
                generate_summaries=False
            )
        )

    def test_build_tree_from_sections(self, extractor):
        """Test building tree from flat section list."""
        sections = [
            {"title": "Article I", "page": 1, "level": 1},
            {"title": "Section 1.01", "page": 1, "level": 2},
            {"title": "Section 1.02", "page": 5, "level": 2},
            {"title": "Article II", "page": 10, "level": 1},
            {"title": "Section 2.01", "page": 10, "level": 2},
        ]

        root = extractor._build_tree_from_sections(sections, total_pages=20)

        assert root.title == "Document"
        assert len(root.children) == 2  # Article I and Article II

        article1 = root.children[0]
        assert article1.title == "Article I"
        assert len(article1.children) == 2  # Section 1.01 and 1.02

        article2 = root.children[1]
        assert article2.title == "Article II"
        assert article2.start_page == 10

    def test_compute_end_pages(self, extractor):
        """Test computing end pages for nodes."""
        root = DocumentNode(id="root", title="Document", level=0, start_page=1)
        child1 = DocumentNode(id="1", title="Section 1", level=1, start_page=1)
        child2 = DocumentNode(id="2", title="Section 2", level=1, start_page=10)
        root.children = [child1, child2]

        extractor._compute_end_pages(root, total_pages=20)

        assert child1.end_page == 9
        assert child2.end_page == 20

    def test_find_title_in_pages(self, extractor):
        """Test finding section title in page text."""
        page_texts = [
            "Introduction to the document",
            "ARTICLE I DEFINITIONS",
            "Section 1.01 Defined Terms",
        ]

        # Exact match
        result = extractor._find_title_in_pages("ARTICLE I DEFINITIONS", page_texts)
        assert result == 2  # Page 2 (1-indexed)

        # Case insensitive
        result = extractor._find_title_in_pages("article i definitions", page_texts)
        assert result == 2

        # Not found
        result = extractor._find_title_in_pages("ARTICLE II", page_texts)
        assert result is None

    @pytest.mark.asyncio
    async def test_programmatic_toc_parsing_without_llm(self, tmp_path):
        fitz = pytest.importorskip("fitz")

        pdf_path = tmp_path / "toc_sample.pdf"
        doc = fitz.open()
        page1 = doc.new_page()
        page1.insert_text((72, 72), "TABLE OF CONTENTS", fontsize=14)
        page1.insert_text((72, 110), "ARTICLE 1 DEFINITIONS", fontsize=11)
        page1.insert_text((72, 130), "1", fontsize=11)
        page1.insert_text((72, 150), "Section 1.01. Certain Defined Terms. ......... 1", fontsize=11)
        page1.insert_text((72, 170), "ARTICLE 2 COVENANTS", fontsize=11)
        page1.insert_text((72, 190), "5", fontsize=11)
        page1.insert_text((72, 210), "Section 2.01. Financial Covenant. ............. 5", fontsize=11)

        for _ in range(6):
            p = doc.new_page()
            p.insert_text((72, 72), "Body text", fontsize=11)
        doc.save(str(pdf_path))
        doc.close()

        local_extractor = DocumentStructureExtractor(
            claude_client=None,
            config=StructureExtractionConfig(generate_summaries=False),
        )
        structure = await local_extractor.extract(str(pdf_path))

        assert structure.mode_used == ExtractionMode.TOC_WITH_PAGES
        assert len(structure.root.children) >= 2
        assert structure.root.children[0].title.startswith("ARTICLE 1")


class TestDocumentNode:
    """Tests for DocumentNode."""

    def test_page_count(self):
        """Test page count calculation."""
        node = DocumentNode(
            id="1",
            title="Test",
            level=1,
            start_page=5,
            end_page=10
        )
        assert node.page_count == 6

    def test_page_count_no_end(self):
        """Test page count when end_page is None."""
        node = DocumentNode(
            id="1",
            title="Test",
            level=1,
            start_page=5,
            end_page=None
        )
        assert node.page_count == 1

    def test_to_dict(self):
        """Test serialization to dict."""
        node = DocumentNode(
            id="1",
            title="Test Section",
            level=1,
            start_page=5,
            end_page=10,
            summary="A test section",
            children=[]
        )

        data = node.to_dict()

        assert data["id"] == "1"
        assert data["title"] == "Test Section"
        assert data["level"] == 1
        assert data["start_page"] == 5
        assert data["end_page"] == 10
        assert data["summary"] == "A test section"

    def test_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "id": "1",
            "title": "Test Section",
            "level": 1,
            "start_page": 5,
            "end_page": 10,
            "summary": "A test section",
            "children": []
        }

        node = DocumentNode.from_dict(data)

        assert node.id == "1"
        assert node.title == "Test Section"
        assert node.level == 1
        assert node.start_page == 5
        assert node.end_page == 10
