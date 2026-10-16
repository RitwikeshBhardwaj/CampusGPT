import importlib
import shutil
from pathlib import Path

import pytest

from app.config import settings
from tests.conftest import write_sample_pdf


def test_ingest_pdf_full_flow(tmp_path, monkeypatch):
    # Set up isolated data dirs
    data_dir = tmp_path / "data"
    pdf_dir = data_dir / "pdfs"
    chroma_dir = data_dir / "chroma"
    db_path = data_dir / "c.db"
    pdf_dir.mkdir(parents=True)
    chroma_dir.mkdir(parents=True)
    monkeypatch.setenv("CAMPUSGPT_DATA_DIR", str(data_dir))
    settings.data_dir = data_dir
    settings.ensure_dirs()

    from app.ingest_pipeline import ingest_pdf

    src = tmp_path / "src.pdf"
    write_sample_pdf(src, ["Page one text. " * 50, "Page two text. " * 50])
    saved_path = tmp_path / "incoming.pdf"
    shutil.copy(src, saved_path)

    result = ingest_pdf(saved_path, "regulations.pdf")
    assert result["filename"] == "regulations.pdf"
    assert result["pages"] >= 1
    assert result["chunks"] >= 1
    assert (pdf_dir / "regulations.pdf").exists()  # saved with original name