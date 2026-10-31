import sys
from types import SimpleNamespace
from pathlib import Path

import pypdf
import pytest

from app.pdf_utils import PDFExtractionError, extract_pages


def test_extract_pages_returns_page_numbers_and_text(tmp_path):
    from tests.conftest import write_sample_pdf
    pdf = tmp_path / "sample.pdf"
    write_sample_pdf(pdf, ["Hello page one", "Second page content"])
    pages = extract_pages(pdf)
    assert pages == [(1, "Hello page one"), (2, "Second page content")]


def test_extract_pages_raises_on_encrypted_pdf(tmp_path):
    from tests.conftest import write_sample_pdf
    pdf = tmp_path / "enc.pdf"
    write_sample_pdf(pdf, ["secret"])
    reader = pypdf.PdfReader(str(pdf))
    writer = pypdf.PdfWriter()
    for p in reader.pages:
        writer.add_page(p)
    writer.encrypt("hunter2")
    out = tmp_path / "enc_out.pdf"
    with open(out, "wb") as f:
        writer.write(f)
    with pytest.raises(PDFExtractionError):
        extract_pages(out)


def test_extract_pages_uses_ocr_for_pages_without_text(tmp_path, monkeypatch):
    from tests.conftest import write_sample_pdf

    pdf = tmp_path / "scanned.pdf"
    write_sample_pdf(pdf, ["", "Existing text"])

    class OCRPage:
        def get_textpage_ocr(self, *, language, dpi, full):
            assert language == "eng"
            assert dpi == 300
            assert full is True
            return object()

        def get_text(self, *, textpage):
            assert textpage is not None
            return "Recognized scanned text"

    class OCRDocument:
        def __getitem__(self, index):
            assert index == 0
            return OCRPage()

        def close(self):
            pass

    monkeypatch.setitem(sys.modules, "pymupdf", SimpleNamespace(open=lambda _: OCRDocument()))

    assert extract_pages(pdf) == [(1, "Recognized scanned text"), (2, "Existing text")]


def test_extract_pages_reports_ocr_failure(tmp_path, monkeypatch):
    from tests.conftest import write_sample_pdf

    pdf = tmp_path / "scanned.pdf"
    write_sample_pdf(pdf, [""])

    class OCRPage:
        def get_textpage_ocr(self, **kwargs):
            raise RuntimeError("Tesseract is not installed")

    class OCRDocument:
        def __getitem__(self, index):
            return OCRPage()

        def close(self):
            pass

    monkeypatch.setitem(sys.modules, "pymupdf", SimpleNamespace(open=lambda _: OCRDocument()))

    with pytest.raises(PDFExtractionError, match="OCR failed on page 1.*Tesseract"):
        extract_pages(pdf)
