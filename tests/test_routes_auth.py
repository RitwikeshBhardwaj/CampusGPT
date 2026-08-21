"""Tests for auth routes: login, logout, me."""

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.db import create_user, init_db


def _make_app(tmp_path, monkeypatch):
    """Build a minimal app with only the auth router and an isolated data dir."""
    monkeypatch.setenv("CAMPUSGPT_DATA_DIR", str(tmp_path))
    from app.config import settings
    settings.data_dir = tmp_path
    init_db(settings.db_path)

    from fastapi import FastAPI
    from app.routes_auth import router as auth_router
    app = FastAPI()
    app.include_router(auth_router)
    return app


def _seed_user(db_path, username="alice", password="pw123", role="admin"):
    return create_user(db_path, username, hash_password(password), role)


def test_login_success_sets_cookie(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = __import__("app.config", fromlist=["settings"]).settings.db_path
    uid = _seed_user(db)

    client = TestClient(app)
    r = client.post("/api/auth/login", json={"username": "alice", "password": "pw123"})
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == uid
    assert data["username"] == "alice"
    assert data["role"] == "admin"
    # Cookie was set
    assert "campusgpt_session" in r.headers.get("set-cookie", "")


def test_login_wrong_password(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = __import__("app.config", fromlist=["settings"]).settings.db_path
    _seed_user(db)

    client = TestClient(app)
    r = client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
    assert r.status_code == 401
    assert "set-cookie" not in r.headers or "campusgpt_session=" not in r.headers.get("set-cookie", "").split(";")[0]


def test_login_unknown_user(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = TestClient(app)
    r = client.post("/api/auth/login", json={"username": "ghost", "password": "x"})
    assert r.status_code == 401


def test_login_missing_fields(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = TestClient(app)
    r = client.post("/api/auth/login", json={"username": "", "password": ""})
    assert r.status_code == 400


def test_me_requires_auth(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = TestClient(app)
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_after_login(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = __import__("app.config", fromlist=["settings"]).settings.db_path
    uid = _seed_user(db, role="student")

    client = TestClient(app)
    client.post("/api/auth/login", json={"username": "alice", "password": "pw123"})
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == uid
    assert data["role"] == "student"


def test_logout_clears_session(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = __import__("app.config", fromlist=["settings"]).settings.db_path
    _seed_user(db)

    client = TestClient(app)
    client.post("/api/auth/login", json={"username": "alice", "password": "pw123"})
    r = client.post("/api/auth/logout")
    assert r.status_code == 204
    # After logout, /me should be 401
    r2 = client.get("/api/auth/me")
    assert r2.status_code == 401