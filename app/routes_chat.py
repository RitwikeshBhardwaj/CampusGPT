"""Chat route: POST /api/chat — retrieve, generate, persist messages."""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.answer import generate_answer
from app.auth import require_user
from app.config import settings
from app.db import (
    add_message,
    create_conversation,
    get_conversation,
    init_db,
)
from app.log_config import log_chat_response, logger
from app.models import AnswerResponse
from app.retrieve import retrieve

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    question: str
    conversation_id: int | None = None


@router.post("/chat", response_model=AnswerResponse)
def chat(body: ChatRequest, user: dict = Depends(require_user)):
    """Answer a question, persist user + assistant messages to a conversation."""
    init_db(settings.db_path)

    question = body.question.strip()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty",
        )

    logger.info(
        "chat_request",
        extra={
            "event": "chat_request",
            "user_id": user["id"],
            "question": question,
            "conversation_id": body.conversation_id,
        },
    )

    conv_id = body.conversation_id
    if conv_id is None:
        title = question[:60] + ("…" if len(question) > 60 else "")
        conv_id = create_conversation(settings.db_path, user["id"], title)
    else:
        conv = get_conversation(settings.db_path, conv_id, user["id"])
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )

    sources = retrieve(question, top_k=settings.top_k)
    result = generate_answer(question, sources)

    log_chat_response(
        user_id=user["id"],
        refused=result.refused,
        num_citations=len(result.citations),
        warning=result.warning,
    )

    citations_json = (
        json.dumps([c.model_dump() for c in result.citations])
        if result.citations
        else None
    )

    # Persist the user's question.
    add_message(
        settings.db_path,
        conv_id=conv_id,
        role="user",
        content=question,
    )
    # Persist the assistant's response.
    add_message(
        settings.db_path,
        conv_id=conv_id,
        role="assistant",
        content=result.answer,
        citations_json=citations_json,
        refused=result.refused,
    )

    return AnswerResponse(
        answer=result.answer,
        citations=result.citations,
        refused=result.refused,
        warning=result.warning,
        closest_source=result.closest_source,
    )