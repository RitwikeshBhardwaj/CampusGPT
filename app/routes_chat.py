"""Chat route: POST /api/chat — thin HTTP layer over the chat service."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.auth import require_user
from app.chat_service import run_chat, stream_chat
from app.models import AnswerResponse

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    question: str
    conversation_id: int | None = None


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ValueError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    raise exc


@router.post("/chat", response_model=AnswerResponse)
def chat(body: ChatRequest, user: dict = Depends(require_user)):
    """Answer a question, persist user + assistant messages to a conversation."""
    try:
        return run_chat(body.question, body.conversation_id, user)
    except (ValueError, LookupError) as exc:
        raise _http_error(exc) from exc


@router.post("/chat/stream")
async def chat_stream(body: ChatRequest, user: dict = Depends(require_user)):
    """Stream the answer as server-sent events, then a final event with citations."""
    events = stream_chat(body.question, body.conversation_id, user)
    try:
        # Validation happens inside the generator, so pull the first event now
        # to surface an empty question or unknown conversation as an HTTP error.
        first = await events.__anext__()
    except (ValueError, LookupError) as exc:
        raise _http_error(exc) from exc

    async def body_iter():
        yield first
        async for event in events:
            yield event

    return StreamingResponse(body_iter(), media_type="text/event-stream")
