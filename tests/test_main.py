from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert data["status"] in ("ok", "degraded")


def test_health_deep_endpoint():
    r = client.get("/api/health/deep")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "ollama" in data
    assert "chroma" in data
    assert "latency_ms" in data["ollama"]
    assert "latency_ms" in data["chroma"]
