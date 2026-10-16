"""Conversation routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import require_user
from app.config import settings
from app.db import (
    create_conversation,
    delete_conversation,
    get_conversation,
    get_messages,
    init_db,
    list_conversations,
)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class ConversationCreate(BaseModel):
    title: str | None = None


class ConversationResponse(BaseModel):
    id: int
    title: str | None
    created_at: str


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    citations_json: str | None
    refused: bool
    created_at: str


def _to_conv_response(conv: dict) -> ConversationResponse:
    return ConversationResponse(
        id=conv["id"],
        title=conv["title"],
        created_at=conv["created_at"],
    )


def _to_msg_response(msg: dict) -> MessageResponse:
    return MessageResponse(
        id=msg["id"],
        conversation_id=msg["conversation_id"],
        role=msg["role"],
        content=msg["content"],
        citations_json=msg["citations_json"],
        refused=bool(msg["refused"]),
        created_at=msg["created_at"],
    )


@router.get("", response_model=list[ConversationResponse])
def list_conversations_route(user: dict = Depends(require_user)):
    """List current user's conversations."""
    init_db(settings.db_path)
    return [_to_conv_response(c) for c in list_conversations(settings.db_path, user["id"])]


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation_route(body: ConversationCreate, user: dict = Depends(require_user)):
    """Create a new conversation for the current user."""
    init_db(settings.db_path)
    conv_id = create_conversation(settings.db_path, user["id"], body.title)
    conv = get_conversation(settings.db_path, conv_id, user["id"])
    return _to_conv_response(conv)


@router.delete("/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation_route(conv_id: int, user: dict = Depends(require_user)):
    """Delete a conversation. Owner only."""
    init_db(settings.db_path)
    ok = delete_conversation(settings.db_path, conv_id, user["id"])
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return None


@router.get("/{conv_id}/messages", response_model=list[MessageResponse])
def get_conversation_messages(conv_id: int, user: dict = Depends(require_user)):
    """Get messages for a conversation. Owner only."""
    init_db(settings.db_path)
    conv = get_conversation(settings.db_path, conv_id, user["id"])
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return [_to_msg_response(m) for m in get_messages(settings.db_path, conv_id, user["id"])]