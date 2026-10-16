"""Structured JSON request logging."""
import json
import logging
import time
from typing import Any


class JsonFormatter(logging.Formatter):
    """Format log records as JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        obj: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Include all non-standard attributes from extra dict
        for key, value in record.__dict__.items():
            if key in ("name", "levelname", "levelno", "pathname", "filename",
                       "module", "exc_info", "exc_text", "stack_info",
                       "timestamp", "message", "asctime", "msg", "args",
                       "created", "msecs", "relativeCreated", "thread",
                       "threadName", "processName", "process"):
                continue
            if isinstance(value, (str, int, float, bool, type(None))):
                obj[key] = value
        return json.dumps(obj, default=str)


def setup_logging() -> logging.Logger:
    """Configure and return the campusgpt logger."""
    logger = logging.getLogger("campusgpt")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    return logger


logger = setup_logging()


def log_retrieval(query: str, top_k: int, num_results: int, persist_dir: str) -> None:
    """Log a retrieval event with structured fields."""
    logger.info(
        "retrieval",
        extra={
            "event": "retrieval",
            "query": query,
            "top_k": top_k,
            "num_results": num_results,
            "persist_dir": persist_dir,
        },
    )


def log_chat_response(user_id: int, refused: bool, num_citations: int, warning: str | None) -> None:
    """Log a chat response event."""
    logger.info(
        "chat_response",
        extra={
            "event": "chat_response",
            "user_id": user_id,
            "refused": refused,
            "citations_count": num_citations,
            "warning": warning,
        },
    )


class LoggingMiddleware:
    """FastAPI middleware that logs each HTTP request as structured JSON."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.time()
        method = scope["method"]
        path = scope["path"]
        response_status = [None]
        user_id = [None]

        # Try to extract user_id from scope state (set by auth middleware if any)
        if "user" in scope:
            user_id[0] = scope["user"].get("id")

        original_send = send

        async def capturing_send(message):
            if message["type"] == "http.response.start":
                response_status[0] = message["status"]
            await original_send(message)

        await self.app(scope, receive, capturing_send)

        duration_ms = round((time.time() - start) * 1000, 2)
        status = response_status[0] or 0

        logger.info(
            "request",
            extra={
                "event": "request",
                "method": method,
                "path": path,
                "status_code": status,
                "duration_ms": duration_ms,
                "user_id": user_id[0],
            },
        )
