"""Tests for DOCX and TXT document ingestion.

Verify that .docx and .txt files can be uploaded, extracted, and chunked
alongside PDFs.
"""

from pathlib import Path
import tempfile

import pytest

from app.ingest_pipeline import ingest_document
from app.config import settings


def test_ingest_txt_file(tmp_path, monkeypatch):
    """A plain text file is extracted, chunked, and indexed."""
    monkeypatch.setenv("CAMPUSGPT_DATA_DIR", str(tmp_path))
    settings.data_dir = tmp_path
    settings.ensure_dirs()

    from app.db import init_db, get_document
    init_db(settings.db_path)

    txt_content = "Attendance requirement is 75 percent. Registration opens June 1."
    txt_file = tmp_path / "rules.txt"
    txt_file.write_text(txt_content, encoding="utf-8")

    result = ingest_document(txt_file, "rules.txt")

    assert result["filename"] == "rules.txt"
    assert result["pages"] == 1
    assert result["chunks"] >= 1

    doc = get_document(settings.db_path, result["doc_id"])
    assert doc["filename"] == "rules.txt"


def test_ingest_docx_file(tmp_path, monkeypatch):
    """A .docx file is extracted, chunked, and indexed."""
    monkeypatch.setenv("CAMPUSGPT_DATA_DIR", str(tmp_path))
    settings.data_dir = tmp_path
    settings.ensure_dirs()

    from app.db import init_db, get_document
    init_db(settings.db_path)

    # Create a minimal valid .docx using python-docx
    try:
        from docx import Document
    except ImportError:
        pytest.skip("python-docx not installed")

    doc = Document()
    doc.add_paragraph("Hostel fee is 12000 per semester.")
    doc.add_paragraph("Library deposit is 2000 refundable.")
    docx_file = tmp_path / "fees.docx"
    doc.save(str(docx_file))

    result = ingest_document(docx_file, "fees.docx")

    assert result["filename"] == "fees.docx"
    assert result["pages"] >= 1
    assert result["chunks"] >= 1

    stored_doc = get_document(settings.db_path, result["doc_id"])
    assert stored_doc["filename"] == "fees.docx"


def test_ingest_multipage_txt(tmp_path, monkeypatch):
    """A large text file produces multiple chunks."""
    monkeypatch.setenv("CAMPUSGPT_DATA_DIR", str(tmp_path))
    settings.data_dir = tmp_path
    settings.ensure_dirs()

    from app.db import init_db
    init_db(settings.db_path)

    # Generate a text file large enough to produce multiple chunks (target_chars=2000)
    # Each sentence is ~50 chars, so we need 50+ sentences to guarantee 2+ chunks
    sentences = []
    for i in range(60):
        sentences.append(f"This is sentence number {i} discussing university policies and regulations for students. ")
    txt_content = " ".join(sentences)
    txt_file = tmp_path / "handbook.txt"
    txt_file.write_text(txt_content, encoding="utf-8")

    result = ingest_document(txt_file, "handbook.txt")

    # With 60 sentences of ~80 chars each = ~4800 chars, we should get at least 2 chunks
    assert result["chunks"] >= 2
