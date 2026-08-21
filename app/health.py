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
