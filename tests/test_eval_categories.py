"""Category tests for RAG evaluation behaviors.

No live LLM is required. Retrieval tests use the real embedder (skipped
when the model cannot load, matching tests/test_eval.py). The refusal
test asserts the model is never called for out-of-scope questions.
"""

import pytest

from app.answer import generate_answer, should_refuse
from app.retrieve import Source, retrieve, add_chunks
from app.ingest import Chunk


@pytest.fixture
def chroma_dir(tmp_path):
    d = tmp_path / "chroma"
    d.mkdir()
    return d


def _model():
    """Lazy-load the real embedding model; skip test if offline."""
    pytest.importorskip("sentence_transformers")
    from sentence_transformers import SentenceTransformer
    try:
        return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    except Exception:
        pytest.skip("Embedding model not available offline")


def test_multi_document_synthesis_retrieves_both_files(chroma_dir):
    """A question needing two files retrieves chunks from both documents."""
    model = _model()
    handbook = [
        Chunk("Tuition is 45000 per semester.", 1, 0),
        Chunk("Hostel fee is 12000 per semester.", 2, 0),
    ]
    fees = [
        Chunk("Library deposit is 2000 refundable.", 1, 0),
        Chunk("Exam fee is 1500 per year.", 2, 0),
    ]
    add_chunks(doc_id=1, doc_name="handbook.pdf", chunks=handbook, model=model, persist_dir=chroma_dir)
    add_chunks(doc_id=2, doc_name="fees.pdf", chunks=fees, model=model, persist_dir=chroma_dir)

    results = retrieve("total semester cost including hostel and library", top_k=6, model=model, persist_dir=chroma_dir)
    doc_names = {r.doc_name for r in results}
    assert "handbook.pdf" in doc_names, f"handbook missing; got {doc_names}"
    assert "fees.pdf" in doc_names, f"fees missing; got {doc_names}"


def test_out_of_scope_refuses_without_calling_llm(monkeypatch):
    """Out-of-scope question refuses via should_refuse; LLM is never called."""
    sources = [
        Source(1, "handbook.pdf", 1, 0, "Tuition is 45000 per semester.", 0.20),
        Source(2, "handbook.pdf", 2, 0, "Hostel fee is 12000 per semester.", 0.15),
    ]
    assert should_refuse(sources) is True

    called = {"llm": False}

    async def fake_post(*args, **kwargs):
        called["llm"] = True
        raise AssertionError("LLM should not be called for an out-of-scope question")

    import app.answer as answer_mod

    monkeypatch.setattr(answer_mod.httpx.AsyncClient, "post", fake_post)

    result = generate_answer("What is the capital of France?", sources)
    assert result.refused is True
    assert result.answer == "I don't have enough information in the provided documents to answer this question."
    assert result.citations == []
    assert called["llm"] is False
    assert result.closest_source is not None
