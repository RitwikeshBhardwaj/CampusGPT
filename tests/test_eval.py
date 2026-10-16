"""Eval set runner — runs each question through retrieve and checks keywords."""
import json
from pathlib import Path

import pytest

from app.ingest import Chunk
from app.retrieve import add_chunks, get_collection, retrieve
from app.answer import should_refuse


@pytest.fixture
def chroma_dir(tmp_path):
    d = tmp_path / "chroma"
    d.mkdir()
    return d


@pytest.fixture
def seeded_corpus(chroma_dir):
    """Seed a small in-memory corpus into ChromaDB."""
    from sentence_transformers import SentenceTransformer
    try:
        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    except Exception:
        pytest.skip("Embedding model not available offline")

    chunks = [
        Chunk("Graduation requires 120 credits minimum.", 1, 0),
        Chunk("Hostel renewal needs identity proof and fee receipt.", 2, 0),
        Chunk("Scholarship eligibility requires CGPA 8.5 or higher.", 3, 0),
        Chunk("Attendance requirement is 75 percent.", 4, 0),
        Chunk("Registration opens on June 1 every year.", 5, 0),
        Chunk("Students must submit documents and application form before the deadline.", 6, 0),
        Chunk("Fee payment deadline is the last day of the month.", 7, 0),
        Chunk("Department change is allowed only during the first week of enrollment.", 8, 0),
        Chunk("The procedure for issuing transcripts takes five working days.", 9, 0),
        Chunk("Apply for a leave of absence by submitting the request to the office.", 10, 0),
    ]
    add_chunks(doc_id=1, doc_name="handbook.pdf", chunks=chunks, model=model, persist_dir=chroma_dir)
    return model


def load_eval_questions():
    path = Path(__file__).parent / "eval_questions.json"
    with open(path) as f:
        return json.load(f)


def test_eval_retrieval_top_hit_precision(chroma_dir, seeded_corpus):
    """The top retrieved hit for a fact question should contain the expected fact."""
    cases = [
        ("What is the minimum graduation credit requirement?", "120 credits"),
        ("What is the scholarship eligibility?", "CGPA 8.5"),
        ("What is the attendance policy?", "75 percent"),
    ]
    for question, expected_fact in cases:
        results = retrieve(question, top_k=3, model=seeded_corpus, persist_dir=chroma_dir)
        assert results, f"No results for '{question}'"
        assert expected_fact.lower() in results[0].text.lower(), (
            f"Top hit for '{question}' does not contain '{expected_fact}'. "
            f"Got: {results[0].text!r}"
        )


def test_eval_retrieval_matches_keywords(chroma_dir, seeded_corpus):
    """Each eval question should retrieve passages containing the expected keywords."""
    questions = load_eval_questions()
    assert len(questions) == 10, "Eval set must contain exactly 10 question/keyword pairs"

    for item in questions:
        question = item["question"]
        expected_keywords = [kw.lower() for kw in item["keywords"]]
        results = retrieve(question, top_k=3, model=seeded_corpus, persist_dir=chroma_dir)

        # Build a lowercase corpus of all retrieved text
        retrieved_text = " ".join(r.text.lower() for r in results)

        # At least one expected keyword should appear in retrieved text
        matched = [kw for kw in expected_keywords if kw in retrieved_text]
        assert len(matched) >= 1, (
            f"Question '{question}' did not match any keywords in retrieved passages. "
            f"Retrieved: {retrieved_text[:200]}"
        )
