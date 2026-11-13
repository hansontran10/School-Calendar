import pytest

from app.extraction.pdf import PdfError, pdf_to_text
from tests.pdfgen import SAMPLE_LINES, make_pdf


def test_text_pdf_is_read():
    text = pdf_to_text(make_pdf(SAMPLE_LINES))
    assert "Exam 1 in class on Thursday, February 18." in text
    assert "Lab Report 1" in text


def test_non_pdf_is_rejected():
    with pytest.raises(PdfError, match="not a PDF"):
        pdf_to_text(b"hello world")


def test_pdf_without_text_is_rejected():
    with pytest.raises(PdfError, match="scanned"):
        pdf_to_text(make_pdf(["hi"]))


def test_large_pdf_is_rejected():
    with pytest.raises(PdfError, match="10 MB"):
        pdf_to_text(b"%PDF" + b"0" * (10 * 1024 * 1024 + 1))


def test_corrupt_pdf_is_rejected():
    with pytest.raises(PdfError):
        pdf_to_text(b"%PDF-1.4\nnot really a pdf")
