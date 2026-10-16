"""Tests for document routes: upload, list, delete."""

import io

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.config import settings
from app.db import create_user, init_db


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("CAMPUSGPT_DATA_DIR", str(tmp_path))
    settings.data_dir = tmp_path
    init_db(settings.db_path)
    settings.ensure_dirs()

    from fastapi import FastAPI
    from app.routes_auth import router as auth_router
    from app.routes_documents import router as docs_router
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(docs_router)
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


def _make_pdf_bytes(text="Page one content about testing.") -> bytes:
    """Generate a minimal valid PDF in memory using the conftest helper."""
    from tests.conftest import write_sample_pdf
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    write_sample_pdf(tmp.name, [text])
    with open(tmp.name, "rb") as f:
        data = f.read()
    import os
    os.unlink(tmp.name)
    return data


def test_admin_can_upload_pdf(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_user(db, "admin", "admin123", "admin")

    client = _make_authenticated_client(app, "admin", "admin123")
    pdf = _make_pdf_bytes()
    r = client.post(
        "/api/documents",
        files={"file": ("test.pdf", io.BytesIO(pdf), "application/pdf")},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["doc_id"] == 1
    assert data["filename"] == "test.pdf"
    assert data["pages"] >= 1
    assert data["chunks"] >= 1


def test_student_cannot_upload_pdf(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_user(db, "alice", "pw123", "student")

    client = _make_authenticated_client(app, "alice", "pw123")
    pdf = _make_pdf_bytes()
    r = client.post(
        "/api/documents",
        files={"file": ("test.pdf", io.BytesIO(pdf), "application/pdf")},
    )
    assert r.status_code == 403


def test_upload_non_pdf_rejected(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_user(db, "admin", "admin123", "admin")

    client = _make_authenticated_client(app, "admin", "admin123")
    r = client.post(
        "/api/documents",
        files={"file": ("test.txt", io.BytesIO(b"not a pdf"), "text/plain")},
    )
    assert r.status_code == 400
    assert "PDF" in r.json()["detail"]


def test_list_documents(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_user(db, "admin", "admin123", "admin")
    _seed_user(db, "alice", "pw123", "student")

    admin_client = _make_authenticated_client(app, "admin", "admin123")
    pdf = _make_pdf_bytes()
    r = admin_client.post(
        "/api/documents",
        files={"file": ("doc1.pdf", io.BytesIO(pdf), "application/pdf")},
    )
    assert r.status_code == 201

    # Student can list
    student_client = _make_authenticated_client(app, "alice", "pw123")
    r2 = student_client.get("/api/documents")
    assert r2.status_code == 200
    docs = r2.json()
    assert len(docs) == 1
    assert docs[0]["filename"] == "doc1.pdf"


def test_student_cannot_delete(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_user(db, "admin", "admin123", "admin")
    _seed_user(db, "alice", "pw123", "student")

    admin_client = _make_authenticated_client(app, "admin", "admin123")
    pdf = _make_pdf_bytes()
    r = admin_client.post(
        "/api/documents",
        files={"file": ("doc1.pdf", io.BytesIO(pdf), "application/pdf")},
    )
    doc_id = r.json()["doc_id"]

    student_client = _make_authenticated_client(app, "alice", "pw123")
    r2 = student_client.delete(f"/api/documents/{doc_id}")
    assert r2.status_code == 403


def test_admin_can_delete_document(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_user(db, "admin", "admin123", "admin")

    client = _make_authenticated_client(app, "admin", "admin123")
    pdf = _make_pdf_bytes()
    r = client.post(
        "/api/documents",
        files={"file": ("todelete.pdf", io.BytesIO(pdf), "application/pdf")},
    )
    doc_id = r.json()["doc_id"]

    r2 = client.delete(f"/api/documents/{doc_id}")
    assert r2.status_code == 204

    # Verify gone
    r3 = client.get("/api/documents")
    assert r3.json() == []


def test_delete_nonexistent_document(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    db = settings.db_path
    _seed_user(db, "admin", "admin123", "admin")

    client = _make_authenticated_client(app, "admin", "admin123")
    r = client.delete("/api/documents/999")
    assert r.status_code == 404


def test_unauthenticated_cannot_list_documents(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = TestClient(app)
    r = client.get("/api/documents")
    assert r.status_code == 401