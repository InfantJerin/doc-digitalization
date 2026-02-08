import pytest

from src.tools.pdf_tools import PDFTools, fitz


@pytest.mark.skipif(fitz is None, reason="PyMuPDF not installed")
def test_pdf_tools_page_count_and_read(tmp_path):
    pdf_path = tmp_path / "sample.pdf"

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Borrower: Acme LLC")
    doc.save(str(pdf_path))
    doc.close()

    tools = PDFTools()

    assert tools.pdf_page_count(str(pdf_path)) == 1

    pages = tools.pdf_read_pages(str(pdf_path), [1])
    assert len(pages) == 1
    assert "Borrower" in pages[0]["text"]


@pytest.mark.skipif(fitz is None, reason="PyMuPDF not installed")
def test_pdf_tools_search(tmp_path):
    pdf_path = tmp_path / "search.pdf"

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Interest Rate: SOFR + 2.50%")
    doc.save(str(pdf_path))
    doc.close()

    tools = PDFTools()
    matches = tools.pdf_search(str(pdf_path), "SOFR")

    assert matches
    assert matches[0]["page"] == 1
