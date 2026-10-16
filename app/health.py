import time

from fastapi import APIRouter

from app.config import settings

router = APIRouter()


@router.get("/api/health")
def health():
    try:
        import httpx
        r = httpx.get(f"{settings.ollama_url}/api/tags", timeout=2.0)
        ollama_ok = r.status_code == 200
    except Exception:
        ollama_ok = False

    try:
        from app.retrieve import get_collection
        coll = get_collection(settings.chroma_dir)
        _ = coll.count()
        chroma_ok = True
    except Exception:
        chroma_ok = False

    status = "ok" if (ollama_ok and chroma_ok) else "degraded"
    return {
        "status": status,
        "ollama": ollama_ok,
        "chroma": chroma_ok,
    }


@router.get("/api/health/deep")
def health_deep():
    t0 = time.time()
    ollama_version = None
    ollama_latency = None
    try:
        import httpx
        r = httpx.get(f"{settings.ollama_url}/api/version", timeout=5.0)
        ollama_latency = round((time.time() - t0) * 1000, 2)
        if r.status_code == 200:
            ollama_version = r.json().get("version")
    except Exception:
        ollama_latency = round((time.time() - t0) * 1000, 2)

    t1 = time.time()
    chroma_count = None
    chroma_latency = None
    try:
        from app.retrieve import get_collection
        coll = get_collection(settings.chroma_dir)
        chroma_count = coll.count()
        chroma_latency = round((time.time() - t1) * 1000, 2)
    except Exception:
        chroma_latency = round((time.time() - t1) * 1000, 2)

    return {
        "status": "ok" if (ollama_version and chroma_count is not None) else "degraded",
        "ollama": {
            "version": ollama_version,
            "latency_ms": ollama_latency,
        },
        "chroma": {
            "count": chroma_count,
            "latency_ms": chroma_latency,
        },
    }
