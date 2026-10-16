"""Tests for admin user-management routes."""

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.config import settings
from app.db import create_user, init_db


def _make_app(tmp_path, monkeypatch):
    """Build a minimal app with admin users router + auth router and an isolated data dir."""
    monkeypatch.setenv("CAMPUSGPT_DATA_DIR", str(tmp_path))
    settings.data_dir = tmp_path
    init_db(settings.db_path)

    from fastapi import FastAPI
    from app.routes_auth import router as auth_router
    from app.routes_users import router as users_router
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(users_router)
    return app


def _seed_admin(db_path, username="admin", password="admin123"):
    return create_user(db_path, username, hash_password(password), "admin")


def _seed_student(db_path, username="student", password="student123"):
    return create_user(db_path, username, hash_password(password), "student")


def _login(client, username, password):
    """Helper to login and get session cookie."""
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200
    cookie = r.headers.get("set-cookie", "")
    return cookie


def _make_authenticated_client(app, username, password):
    """Create a TestClient with pre-set auth cookie."""
    client = TestClient(app)
    cookie = _login(client, username, password)
    client.cookies.set("campusgpt_session", cookie.split("campusgpt_session=")[1].split(";")[0])
    return client


def test_admin_can_list_users(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_admin(db)
    _seed_student(db, "alice")
    _seed_student(db, "bob")

    client = _make_authenticated_client(app, "admin", "admin123")
    r = client.get("/api/admin/users")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    usernames = {u["username"] for u in data}
    assert usernames == {"admin", "alice", "bob"}


def test_student_cannot_list_users(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_admin(db)
    _seed_student(db, "alice")

    client = _make_authenticated_client(app, "alice", "student123")
    r = client.get("/api/admin/users")
    assert r.status_code == 403


def test_unauthenticated_cannot_list_users(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = TestClient(app)
    r = client.get("/api/admin/users")
    assert r.status_code == 401


def test_admin_can_create_student(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_admin(db)

    client = _make_authenticated_client(app, "admin", "admin123")
    r = client.post("/api/admin/users", json={"username": "newstudent", "password": "pw123", "role": "student"})
    assert r.status_code == 201
    data = r.json()
    assert data["username"] == "newstudent"
    assert data["role"] == "student"
    assert "id" in data


def test_admin_can_create_admin(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_admin(db)

    client = _make_authenticated_client(app, "admin", "admin123")
    r = client.post("/api/admin/users", json={"username": "newadmin", "password": "pw123", "role": "admin"})
    assert r.status_code == 201
    data = r.json()
    assert data["role"] == "admin"


def test_create_user_duplicate_username(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_admin(db)

    client = _make_authenticated_client(app, "admin", "admin123")
    r1 = client.post("/api/admin/users", json={"username": "dup", "password": "pw123", "role": "student"})
    assert r1.status_code == 201
    r2 = client.post("/api/admin/users", json={"username": "dup", "password": "pw456", "role": "student"})
    assert r2.status_code == 409
    assert "already exists" in r2.json()["detail"]


def test_create_user_invalid_role(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_admin(db)

    client = _make_authenticated_client(app, "admin", "admin123")
    r = client.post("/api/admin/users", json={"username": "badrole", "password": "pw123", "role": "superuser"})
    assert r.status_code == 400
    assert "Role must be" in r.json()["detail"]


def test_admin_can_delete_other_user(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_admin(db)
    todelete_id = _seed_student(db, "todelete")

    client = _make_authenticated_client(app, "admin", "admin123")
    r = client.delete(f"/api/admin/users/{todelete_id}")
    assert r.status_code == 204

    # Verify deleted
    r2 = client.get("/api/admin/users")
    usernames = {u["username"] for u in r2.json()}
    assert "todelete" not in usernames


def test_admin_cannot_delete_self(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_admin(db)

    client = _make_authenticated_client(app, "admin", "admin123")
    r = client.delete("/api/admin/users/1")  # admin is id 1
    assert r.status_code == 403
    assert "Cannot delete yourself" in r.json()["detail"]


def test_admin_cannot_delete_nonexistent(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_admin(db)

    client = _make_authenticated_client(app, "admin", "admin123")
    r = client.delete("/api/admin/users/999")
    assert r.status_code == 404


def test_student_cannot_delete_user(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_admin(db)
    _seed_student(db, "alice")

    client = _make_authenticated_client(app, "alice", "student123")
    r = client.delete("/api/admin/users/1")
    assert r.status_code == 403