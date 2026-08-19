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
