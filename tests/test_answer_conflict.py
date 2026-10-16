from app.answer import build_prompt, parse_citations
from app.retrieve import Source


def test_build_prompt_contains_conflict_instruction():
    sources = [
        Source(1, "regulations.pdf", 4, 0, "Graduation requires 120 credits minimum.", 0.9),
        Source(2, "catalog.pdf", 2, 0, "Graduation requires 130 credits minimum.", 0.85),
    ]
    prompt = build_prompt(sources, "How many credits to graduate?")
    assert "disagree" in prompt.lower() or "conflict" in prompt.lower()
    assert "Do not pick one" in prompt or "do not pick one" in prompt.lower()


def test_parse_citations_keeps_both_conflicting_sources():
    sources = [
        Source(1, "regulations.pdf", 4, 0, "120 credits minimum.", 0.9),
        Source(2, "catalog.pdf", 2, 0, "130 credits minimum.", 0.85),
    ]
    answer = "Handbook says 120 credits [1]. Catalog says 130 credits [2]. These conflict."
    cleaned, citations = parse_citations(answer, sources)
    assert len(citations) == 2
    numbers = {c.number for c in citations}
    assert numbers == {1, 2}
    assert citations[0].doc_name == "regulations.pdf"
    assert citations[1].doc_name == "catalog.pdf"
