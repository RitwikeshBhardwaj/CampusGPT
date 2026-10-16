import re
from dataclasses import dataclass

import pytest

from app.models import Citation, AnswerResponse
from app.retrieve import Source
from app.answer import (
    build_prompt,
    parse_citations,
    should_refuse,
    generate_answer,
    AnswerResult,
)


def test_should_refuse_below_threshold():
    srcs = [
        Source(doc_id=1, doc_name="a.pdf", page=1, chunk_index=0, text="irrelevant", score=0.20),
        Source(doc_id=1, doc_name="a.pdf", page=2, chunk_index=1, text="irrelevant", score=0.10),
    ]
    assert should_refuse(srcs) is True


def test_should_not_refuse_above_threshold():
    srcs = [
        Source(doc_id=1, doc_name="a.pdf", page=1, chunk_index=0, text="relevant", score=0.50),
    ]
    assert should_refuse(srcs) is False


def test_parse_citations_keeps_valid_and_drops_hallucinated():
    srcs = [
        Source(doc_id=1, doc_name="handbook.pdf", page=5, chunk_index=0, text="CGPA 8.5 required", score=0.8),
        Source(doc_id=1, doc_name="handbook.pdf", page=10, chunk_index=1, text="120 credits needed", score=0.6),
    ]
    answer = "Scholarship needs CGPA 8.5 [1]. Also 120 credits [2]. Hallucinated [3]."
    cleaned, citations = parse_citations(answer, srcs)
    assert cleaned == "Scholarship needs CGPA 8.5 [1]. Also 120 credits [2]. Hallucinated ."
    assert len(citations) == 2
    assert citations[0].number == 1
    assert citations[0].doc_name == "handbook.pdf"
    assert citations[0].page == 5
    assert "CGPA 8.5" in citations[0].passage
    assert citations[1].number == 2
    assert citations[1].page == 10


def test_parse_citations_empty_when_no_brackets():
    srcs = [Source(doc_id=1, doc_name="a.pdf", page=1, chunk_index=0, text="x", score=0.5)]
    answer = "I don't know"
    cleaned, citations = parse_citations(answer, srcs)
    assert citations == []


def test_build_prompt_formats_sources():
    srcs = [
        Source(doc_id=1, doc_name="regulations.pdf", page=12, chunk_index=0, text="Minimum 120 credits.", score=0.9),
    ]
    prompt = build_prompt(srcs, "What are graduation credits?")
    assert "regulations.pdf, p.12" in prompt
    assert "Minimum 120 credits" in prompt
    assert "[1]" in prompt
    assert "What are graduation credits?" in prompt


@dataclass
class MockResponse:
    text: str


def test_generate_answer_refusal_path(monkeypatch):
    """When sources below threshold, returns refused AnswerResult with closest_source."""
    srcs = [
        Source(doc_id=1, doc_name="a.pdf", page=1, chunk_index=0, text="unrelated", score=0.20),
    ]

    async def mock_post(*args, **kwargs):
        return MockResponse(text="Should not be called")

    import httpx
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    # This test only checks should_refuse logic triggers refusal
    # generate_answer will call should_refuse internally
    result = generate_answer("question", srcs)
    assert result.refused is True
    assert result.answer == "I don't have enough information in the provided documents to answer this question."
    assert result.closest_source is not None
    assert result.closest_source.doc_name == "a.pdf"


def test_parse_citations_drops_hallucinated_large_numbers():
    """[99] (or any number > len(sources)) is dropped; answer text is preserved."""
    srcs = [Source(doc_id=1, doc_name="reg.pdf", page=4, chunk_index=0, text="120 credits.", score=0.9)]
    # Only hallucinated numbers — should return zero citations; meaningful text preserved
    text = "See [99] for more."
    cleaned, citations = parse_citations(text, srcs)
    assert len(citations) == 0
    # The [99] marker is removed; the rest of the text is preserved
    assert "See" in cleaned and "for more" in cleaned