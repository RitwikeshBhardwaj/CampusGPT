"""Chat orchestration: retrieval, generation, and persistence.

Separated from the HTTP route so the route stays thin and this logic
can be tested without a request/response cycle.
"""

import json

from app.answer import (
    build_prompt,
    generate_answer,
    parse_citations,
    should_refuse,
    stream_ollama,
)
from app.config import settings
from app.db import add_message, create_conversation, get_conversation, init_db
from app.log_config import log_chat_response, logger
from app.models import AnswerResponse, Citation
from app.retrieve import retrieve


def _prepare_chat(question: str, conversation_id: int | None, user: dict) -> tuple[str, int]:
    """Validate the question and resolve the conversation to write into.

    Raises ValueError for an empty question and LookupError when the
    given conversation does not belong to the user.
    """
    init_db(settings.db_path)

    question = question.strip()
    if not question:
        raise ValueError("Question cannot be empty")

    logger.info(
        "chat_request",
        extra={
            "event": "chat_request",
            "user_id": user["id"],
            "question": question,
            "conversation_id": conversation_id,
        },
    )

    conv_id = conversation_id
    if conv_id is None:
        title = question[:60] + ("…" if len(question) > 60 else "")
        conv_id = create_conversation(settings.db_path, user["id"], title)
    else:
        conv = get_conversation(settings.db_path, conv_id, user["id"])
        if not conv:
            raise LookupError("Conversation not found")

    return question, conv_id


def _persist_exchange(conv_id: int, question: str, result) -> None:
    citations_json = (
        json.dumps([c.model_dump() for c in result.citations])
        if result.citations
        else None
    )
    add_message(settings.db_path, conv_id=conv_id, role="user", content=question)
    add_message(
        settings.db_path,
        conv_id=conv_id,
        role="assistant",
        content=result.answer,
        citations_json=citations_json,
        refused=result.refused,
    )


def _log_result(user: dict, result) -> None:
    log_chat_response(
        user_id=user["id"],
        refused=result.refused,
        num_citations=len(result.citations),
        warning=result.warning,
    )


async def stream_chat(question: str, conversation_id: int | None, user: dict):
    """Yield SSE events: one `token` event per piece of the answer, then a `final` event.

    A refusal yields only the final event. The exchange is persisted once the answer is complete.
    """
    question, conv_id = _prepare_chat(question, conversation_id, user)
    sources = retrieve(question, top_k=settings.top_k)

    if should_refuse(sources):
        result = generate_answer(question, sources)
        _log_result(user, result)
        _persist_exchange(conv_id, question, result)
        yield _sse("final", _final_payload(result))
        return

    raw = ""
    async for token in stream_ollama(build_prompt(sources, question)):
        raw += token
        yield _sse("token", {"text": token})

    cleaned, citations = parse_citations(raw, sources)
    warning = None
    if not citations and not cleaned.strip().startswith("I don't have enough"):
        warning = "This answer may not be fully grounded in the source documents."
    from app.answer import AnswerResult
    result = AnswerResult(
        answer=cleaned, citations=citations, refused=False,
        warning=warning, closest_source=None,
    )
    _log_result(user, result)
    _persist_exchange(conv_id, question, result)
    yield _sse("final", _final_payload(result))


def _sse(event_type: str, payload: dict) -> str:
    return "data: " + json.dumps({"type": event_type, **payload}) + "\n\n"


def _final_payload(result) -> dict:
    return {
        "answer": result.answer,
        "citations": [c.model_dump() for c in result.citations],
        "refused": result.refused,
        "warning": result.warning,
        "closest_source": result.closest_source.model_dump() if result.closest_source else None,
    }


def run_chat(question: str, conversation_id: int | None, user: dict) -> AnswerResponse:
    """Answer a question and persist both sides of the exchange.

    Raises ValueError for an empty question and LookupError when the
    given conversation does not belong to the user.
    """
    question, conv_id = _prepare_chat(question, conversation_id, user)

    sources = retrieve(question, top_k=settings.top_k)
    result = generate_answer(question, sources)

    _log_result(user, result)
    _persist_exchange(conv_id, question, result)

    return AnswerResponse(
        answer=result.answer,
        citations=result.citations,
        refused=result.refused,
        warning=result.warning,
        closest_source=result.closest_source,
    )
