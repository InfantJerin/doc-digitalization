import pytest

fitz = pytest.importorskip("fitz")

from src.indexing.page_layout_analyzer import PageLayoutAnalyzer


def test_page_layout_analyzer_extracts_basic_layout(tmp_path):
    pdf_path = tmp_path / "sample.pdf"

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Section 1.01 Definitions", fontsize=18)
    page.insert_text((72, 120), "This agreement defines EBITDA and other terms.", fontsize=10)
    page.insert_text((72, 760), "1 Footnote text appears at bottom of page.", fontsize=8)
    doc.save(str(pdf_path))
    doc.close()

    analyzer = PageLayoutAnalyzer()
    layouts = analyzer.analyze_document(pdf_path)

    assert len(layouts) == 1
    assert layouts[0].page_number == 1
    assert layouts[0].headers
    assert any("Section 1.01" in h for h in layouts[0].headers)
    assert layouts[0].word_count > 0
