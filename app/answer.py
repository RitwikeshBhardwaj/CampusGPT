import json
import re
from dataclasses import dataclass
from typing import Optional

import httpx

from app.config import settings
from app.models import Citation
from app.retrieve import Source


@dataclass
class AnswerResult:
    answer: str
    citations: list[Citation]
    refused: bool
    warning: Optional[str]
    closest_source: Optional[Citation]


def should_refuse(sources: list[Source]) -> bool:
    """Return True if best similarity score is below the confidence threshold."""
    if not sources:
        return True
    best = max(s.score for s in sources)
    return best < settings.confidence_threshold


def build_prompt(sources: list[Source], question: str) -> str:
    """Build the RAG prompt with numbered sources."""
    lines = [
        "You are CampusGPT, a university document assistant.",
        "Answer the user's question using ONLY the numbered sources provided below.",
        "Cite sources in your answer as [1], [2], etc.",
        "If the answer is not fully contained in the sources, say \"I don't have",
        "enough information in the provided documents to answer this question.\"",
        "Never make up information.",
        "If the sources disagree on the same fact, quote both versions and state that they conflict.",
        "Do not pick one.",
        "",
        "Sources:",
    ]
    for i, src in enumerate(sources, 1):
        lines.append(f"[{i}] {src.doc_name}, p.{src.page} — \"{src.text}\"")
    lines.append("")
    lines.append(f"User: {question}")
    return "\n".join(lines)


_CITATION_RE = re.compile(r"\[([1-9][0-9]*)\]")


def parse_citations(answer_text: str, sources: list[Source]) -> tuple[str, list[Citation]]:
    """Extract [N] citations, drop hallucinated numbers (N > len(sources))."""
    cited_numbers = set(int(m.group(1)) for m in _CITATION_RE.finditer(answer_text))
    valid_numbers = {n for n in cited_numbers if 1 <= n <= len(sources)}

    # Build citations for valid numbers
    citations = []
    for n in sorted(valid_numbers):
        src = sources[n - 1]
        citations.append(
            Citation(
                number=n,
                doc_name=src.doc_name,
                page=src.page,
                passage=src.text,
            )
        )

    # Remove hallucinated citations from the answer text
    def repl(match):
        n = int(match.group(1))
        return "" if n not in valid_numbers else match.group(0)

    cleaned = _CITATION_RE.sub(repl, answer_text)
    return cleaned, citations


async def _call_ollama(prompt: str) -> str:
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.ollama_url}/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "stream": False,
            },
        )
        resp.raise_for_status()
        return resp.json().get("response", "")


async def stream_ollama(prompt: str):
    """Yield answer text as Ollama produces it."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{settings.ollama_url}/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "stream": True,
            },
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                token = json.loads(line).get("response", "")
                if token:
                    yield token


def generate_answer(question: str, sources: list[Source]) -> AnswerResult:
    """Full answer generation: check threshold, call LLM, parse citations."""
    if should_refuse(sources):
        closest = sources[0] if sources else None
        closest_cit = (
            Citation(
                number=1,
                doc_name=closest.doc_name,
                page=closest.page,
                passage=closest.text,
            )
            if closest
            else None
        )
        return AnswerResult(
            answer="I don't have enough information in the provided documents to answer this question.",
            citations=[],
            refused=True,
            warning=None,
            closest_source=closest_cit,
        )

    prompt = build_prompt(sources, question)
    # Run the async call synchronously
    import asyncio
    response_text = asyncio.run(_call_ollama(prompt))

    cleaned_text, citations = parse_citations(response_text, sources)

    # Warning if no citations and not a refusal
    warning = None
    if not citations and not cleaned_text.strip().startswith("I don't have enough"):
        warning = "This answer may not be fully grounded in the source documents."

    return AnswerResult(
        answer=cleaned_text,
        citations=citations,
        refused=False,
        warning=warning,
        closest_source=None,
    )