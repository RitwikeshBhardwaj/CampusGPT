"""Tests for conversation routes."""

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.config import settings
from app.db import create_user, init_db


def _make_app(tmp_path, monkeypatch):
    """Build a minimal app with auth + conversation routers and isolated data dir."""
    monkeypatch.setenv("CAMPUSGPT_DATA_DIR", str(tmp_path))
    settings.data_dir = tmp_path
    init_db(settings.db_path)

    from fastapi import FastAPI
    from app.routes_auth import router as auth_router
    from app.routes_conversations import router as conv_router
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(conv_router)
    return app


def _seed_user(db_path, username="alice", password="pw123", role="student"):
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


def test_list_conversations_empty(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_user(db)

    client = _make_authenticated_client(app, "alice", "pw123")
    r = client.get("/api/conversations")
    assert r.status_code == 200
    assert r.json() == []


def test_create_and_list_conversation(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_user(db)

    client = _make_authenticated_client(app, "alice", "pw123")
    r = client.post("/api/conversations", json={"title": "My Chat"})
    assert r.status_code == 201
    data = r.json()
    assert data["id"] == 1
    assert data["title"] == "My Chat"
    assert "created_at" in data

    r2 = client.get("/api/conversations")
    assert r2.status_code == 200
    convs = r2.json()
    assert len(convs) == 1
    assert convs[0]["title"] == "My Chat"


def test_create_conversation_no_title(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_user(db)

    client = _make_authenticated_client(app, "alice", "pw123")
    r = client.post("/api/conversations", json={})
    assert r.status_code == 201
    data = r.json()
    assert data["title"] is None


def test_user_cannot_see_other_users_conversations(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    uid1 = _seed_user(db, "alice", "pw123")
    _seed_user(db, "bob", "pw123")

    client1 = _make_authenticated_client(app, "alice", "pw123")
    r = client1.post("/api/conversations", json={"title": "Alice's Chat"})
    assert r.status_code == 201
    conv_id = r.json()["id"]

    client2 = _make_authenticated_client(app, "bob", "pw123")
    r2 = client2.get("/api/conversations")
    assert r2.status_code == 200
    assert r2.json() == []


def test_rename_own_conversation(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_user(db, "alice", "pw123")

    client = _make_authenticated_client(app, "alice", "pw123")
    conv_id = client.post("/api/conversations", json={}).json()["id"]

    r = client.patch(f"/api/conversations/{conv_id}", json={"title": "  Library hours  "})
    assert r.status_code == 200
    assert r.json()["title"] == "Library hours"

    listed = client.get("/api/conversations").json()
    assert listed[0]["title"] == "Library hours"


def test_rename_rejects_empty_title(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_user(db, "alice", "pw123")

    client = _make_authenticated_client(app, "alice", "pw123")
    conv_id = client.post("/api/conversations", json={"title": "Keep me"}).json()["id"]

    for bad in ("", "   ", "x" * 121):
        r = client.patch(f"/api/conversations/{conv_id}", json={"title": bad})
        assert r.status_code == 400

    listed = client.get("/api/conversations").json()
    assert listed[0]["title"] == "Keep me"


def test_cannot_rename_other_users_conversation(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_user(db, "alice", "pw123")
    _seed_user(db, "bob", "pw123")

    client1 = _make_authenticated_client(app, "alice", "pw123")
    conv_id = client1.post("/api/conversations", json={"title": "Alice's"}).json()["id"]

    client2 = _make_authenticated_client(app, "bob", "pw123")
    r = client2.patch(f"/api/conversations/{conv_id}", json={"title": "Stolen"})
    assert r.status_code == 404

    listed = client1.get("/api/conversations").json()
    assert listed[0]["title"] == "Alice's"


def test_delete_own_conversation(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_user(db, "alice", "pw123")

    client = _make_authenticated_client(app, "alice", "pw123")
    r = client.post("/api/conversations", json={"title": "To Delete"})
    assert r.status_code == 201
    conv_id = r.json()["id"]

    r2 = client.delete(f"/api/conversations/{conv_id}")
    assert r2.status_code == 204

    r3 = client.get("/api/conversations")
    assert r3.json() == []


def test_cannot_delete_other_users_conversation(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_user(db, "alice", "pw123")
    _seed_user(db, "bob", "pw123")

    client1 = _make_authenticated_client(app, "alice", "pw123")
    r = client1.post("/api/conversations", json={"title": "Alice's"})
    assert r.status_code == 201
    conv_id = r.json()["id"]

    client2 = _make_authenticated_client(app, "bob", "pw123")
    r2 = client2.delete(f"/api/conversations/{conv_id}")
    assert r2.status_code == 404


def test_delete_nonexistent_conversation(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_user(db, "alice", "pw123")

    client = _make_authenticated_client(app, "alice", "pw123")
    r = client.delete("/api/conversations/999")
    assert r.status_code == 404


def test_get_messages_empty(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_user(db, "alice", "pw123")

    client = _make_authenticated_client(app, "alice", "pw123")
    r = client.post("/api/conversations", json={"title": "Chat"})
    conv_id = r.json()["id"]

    r2 = client.get(f"/api/conversations/{conv_id}/messages")
    assert r2.status_code == 200
    assert r2.json() == []


def test_get_messages_not_owner_returns_404(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_user(db, "alice", "pw123")
    _seed_user(db, "bob", "pw123")

    client1 = _make_authenticated_client(app, "alice", "pw123")
    r = client1.post("/api/conversations", json={"title": "Alice's"})
    conv_id = r.json()["id"]

    client2 = _make_authenticated_client(app, "bob", "pw123")
    r2 = client2.get(f"/api/conversations/{conv_id}/messages")
    assert r2.status_code == 404


def test_unauthenticated_cannot_access_conversations(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = TestClient(app)
    r = client.get("/api/conversations")
    assert r.status_code == 401