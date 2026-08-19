from pathlib import Path

import pytest

from app.retrieve import Source, retrieve, add_chunks, get_collection
from app.ingest import Chunk


@pytest.fixture
def chroma_dir(tmp_path):
    d = tmp_path / "chroma"
    d.mkdir()
    return d


def _model():
    """Lazy-load the real embedding model; skip test if model download fails."""
    pytest.importorskip("sentence_transformers")
    from sentence_transformers import SentenceTransformer
    try:
        return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    except Exception:
        pytest.skip("Embedding model not available offline")


def test_add_and_retrieve_returns_top_k(chroma_dir):
    model = _model()
    chunks = [
        Chunk("Scholarship eligibility requires CGPA 8.5 or higher.", 1, 0),
        Chunk("Graduation requires 120 credits minimum.", 5, 0),
        Chunk("Hostel renewal needs identity proof and fee receipt.", 9, 0),
    ]
    add_chunks(doc_id=1, doc_name="handbook.pdf", chunks=chunks, model=model, persist_dir=chroma_dir)
    results = retrieve("What is the scholarship eligibility?", top_k=2, model=model, persist_dir=chroma_dir)
    assert len(results) == 2
    assert all(isinstance(r, Source) for r in results)
    # Top hit should be the scholarship one
    assert "Scholarship" in results[0].text
    assert results[0].doc_name == "handbook.pdf"
    assert results[0].page == 1
    assert results[0].score > results[1].score


def test_retrieve_returns_metadata(chroma_dir):
    model = _model()
    chunks = [Chunk("Attendance requirement is 75 percent.", 3, 0)]
    add_chunks(doc_id=2, doc_name="rules.pdf", chunks=chunks, model=model, persist_dir=chroma_dir)
    results = retrieve("attendance", top_k=1, model=model, persist_dir=chroma_dir)
    assert results[0].doc_id == 2
    assert results[0].page == 3
