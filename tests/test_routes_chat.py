"""Tests for /api/chat route — message persistence, refusal, ownership."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.config import settings
from app.db import (
    create_user,
    get_messages,
    init_db,
)


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("CAMPUSGPT_DATA_DIR", str(tmp_path))
    settings.data_dir = tmp_path
    init_db(settings.db_path)
    settings.ensure_dirs()

    from fastapi import FastAPI
    from app.routes_auth import router as auth_router
    from app.routes_chat import router as chat_router
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(chat_router)
    return app


def _seed_user(db_path, username, password, role):
    return create_user(db_path, username, hash_password(password), role)


def _login(client, username, password):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200
    cookie = r.headers.get("set-cookie", "")
    return cookie


def _make_authenticated_client(app, username, password):
    client = TestClient(app)
    cookie = _login(client, username, password)
    client.cookies.set("campusgpt_session", cookie.split("campusgpt_session=")[1].split(";")[0])
    return client


def test_chat_creates_conversation_and_persists_messages(tmp_path, monkeypatch):
    """A chat call without conversation_id creates one and persists both messages."""
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_user(db, "alice", "pw123", "student")

    client = _make_authenticated_client(app, "alice", "pw123")

    # Stub retrieve + generate_answer to avoid Ollama / Chroma.
    with patch("app.routes_chat.retrieve") as mock_retrieve, \
         patch("app.routes_chat.generate_answer") as mock_generate:
        from app.models import Citation
        from app.answer import AnswerResult
        from app.retrieve import Source

        mock_retrieve.return_value = [
            Source(
                doc_id=1, doc_name="handbook.pdf", page=1,
                chunk_index=0, text="Registration opens June 1.",
                score=0.8,
            )
        ]
        mock_generate.return_value = AnswerResult(
            answer="Registration opens on June 1 [1].",
            citations=[
                Citation(
                    number=1, doc_name="handbook.pdf", page=1,
                    passage="Registration opens June 1.",
                )
            ],
            refused=False,
            warning=None,
            closest_source=None,
        )

        r = client.post("/api/chat", json={"question": "When does registration open?"})

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["answer"].startswith("Registration")
    assert len(data["citations"]) == 1
    assert data["citations"][0]["doc_name"] == "handbook.pdf"
    assert data["refused"] is False

    # Verify both messages persisted under a new conversation.
    msgs = get_messages(db, conv_id=1, user_id=1)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "When does registration open?"
    assert msgs[1]["role"] == "assistant"
    assert "Registration" in msgs[1]["content"]


def test_chat_persists_refusal(tmp_path, monkeypatch):
    """A refusal persists with refused=1 and citations_json is null."""
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_user(db, "alice", "pw123", "student")

    client = _make_authenticated_client(app, "alice", "pw123")

    with patch("app.routes_chat.retrieve") as mock_retrieve, \
         patch("app.routes_chat.generate_answer") as mock_generate:
        from app.models import Citation
        from app.answer import AnswerResult
        from app.retrieve import Source

        mock_retrieve.return_value = [
            Source(
                doc_id=1, doc_name="handbook.pdf", page=1,
                chunk_index=0, text="About something else entirely.",
                score=0.1,
            )
        ]
        mock_generate.return_value = AnswerResult(
            answer="I don't have enough information in the provided documents to answer this question.",
            citations=[],
            refused=True,
            warning=None,
            closest_source=Citation(
                number=1, doc_name="handbook.pdf", page=1,
                passage="About something else entirely.",
            ),
        )

        r = client.post("/api/chat", json={"question": "What's the weather?"})

    assert r.status_code == 200
    data = r.json()
    assert data["refused"] is True
    assert data["citations"] == []
    assert data["closest_source"] is not None

    msgs = get_messages(db, conv_id=1, user_id=1)
    assert msgs[1]["refused"] == 1
    assert msgs[1]["citations_json"] is None


def test_chat_ownership_enforced(tmp_path, monkeypatch):
    """Cannot post to another user's conversation."""
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_user(db, "alice", "pw123", "student")
    _seed_user(db, "bob", "pw123", "student")

    # Alice creates a conversation by chatting once.
    client1 = _make_authenticated_client(app, "alice", "pw123")
    with patch("app.routes_chat.retrieve") as mock_retrieve, \
         patch("app.routes_chat.generate_answer") as mock_generate:
        from app.answer import AnswerResult
        from app.retrieve import Source

        mock_retrieve.return_value = [
            Source(
                doc_id=1, doc_name="x.pdf", page=1, chunk_index=0,
                text="x", score=0.8,
            )
        ]
        mock_generate.return_value = AnswerResult(
            answer="hi [1]", citations=[], refused=False, warning=None,
            closest_source=None,
        )
        r1 = client1.post("/api/chat", json={"question": "hello"})
        assert r1.status_code == 200

    # Bob tries to use Alice's conversation.
    client2 = _make_authenticated_client(app, "bob", "pw123")
    r2 = client2.post("/api/chat", json={"question": "secret", "conversation_id": 1})
    assert r2.status_code == 404


def test_chat_empty_question_rejected(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_user(db, "alice", "pw123", "student")

    client = _make_authenticated_client(app, "alice", "pw123")
    r = client.post("/api/chat", json={"question": "   "})
    assert r.status_code == 400


def test_chat_unauthenticated_rejected(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = TestClient(app)
    r = client.post("/api/chat", json={"question": "hi"})
    assert r.status_code == 401


def test_chat_uses_existing_conversation(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_user(db, "alice", "pw123", "student")

    client = _make_authenticated_client(app, "alice", "pw123")
    with patch("app.routes_chat.retrieve") as mock_retrieve, \
         patch("app.routes_chat.generate_answer") as mock_generate:
        from app.answer import AnswerResult
        from app.retrieve import Source

        mock_retrieve.return_value = [
            Source(doc_id=1, doc_name="x.pdf", page=1, chunk_index=0, text="x", score=0.8)
        ]
        mock_generate.return_value = AnswerResult(
            answer="a", citations=[], refused=False, warning=None, closest_source=None,
        )
        # First message creates conv 1
        client.post("/api/chat", json={"question": "first"})
        # Second message reuses conv 1
        client.post("/api/chat", json={"question": "second", "conversation_id": 1})

    msgs = get_messages(db, conv_id=1, user_id=1)
    assert len(msgs) == 4  # 2 user, 2 assistant
    assert msgs[0]["content"] == "first"
    assert msgs[2]["content"] == "second"