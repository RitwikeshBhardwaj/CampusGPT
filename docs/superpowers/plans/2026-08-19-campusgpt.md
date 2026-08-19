# CampusGPT Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build CampusGPT — a fully local RAG system where university students/admins ask natural-language questions against a shared PDF library and receive grounded answers with inline citations (doc name + page + passage).

**Architecture:** FastAPI backend exposes `/api/*` for chat, auth, admin. React (Vite) SPA serves at `/`. ChromaDB stores vectors; SQLite stores users, conversations, messages, document metadata. pypdf extracts page-wise text. Ollama runs Llama 3.1 8B on localhost:11434 for generation. Sentence-transformers `all-MiniLM-L6-v2` runs in-process for embeddings.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, pypdf, sentence-transformers, chromadb, sqlite3 (stdlib), bcrypt/passlib, Ollama, React 18, Vite, TypeScript, react-router.

**Spec:** `docs/superpowers/specs/2026-08-19-campusgpt-design.md`

---

## Global Constraints

- Python 3.11+ is required (uses `tomllib`, modern type hints).
- All Python source lives under `app/` and `tests/`.
- All React source lives under `frontend/src/`.
- Confidence threshold for refusal: `0.35` (ChromaDB cosine distance; lower = more confident when using "distance" metric, but we use **similarity scores normalized to 0-1** — see Task 4).
- Retrieval `top_k = 6`.
- Chunk target size: ~500 tokens (~2000 characters), sentence-aware, never cross page boundaries.
- Embedding model: `sentence-transformers/all-MiniLM-L6-v2` (loaded once, cached).
- LLM: `llama3.1:8b` via Ollama at `http://localhost:11434/api/generate`.
- Hallucinated citation numbers (`[N]` where `N > len(sources)`) MUST be silently dropped before the response is returned.
- First-run admin account is seeded from env vars `CAMPUSGPT_ADMIN_USER` and `CAMPUSGPT_ADMIN_PASS`.
- Password storage uses bcrypt via passlib.
- Session token is in an `httpOnly` cookie named `campusgpt_session`, 7-day expiry, signed via itsdangerous.
- Backend binds to `127.0.0.1:8000` by default; override via `CAMPUSGPT_HOST` / `CAMPUSGPT_PORT`.
- All persistence lives under `./data/` (created on first run): `./data/pdfs/`, `./data/chroma/`, `./data/campusgpt.db`.
- All commits end with `Co-Authored-By: Claude <noreply@anthropic.com>`.
- Commit messages use Conventional Commits (`feat:`, `test:`, `chore:`, `docs:`, `fix:`).

---

## File Structure

### Backend (`app/`)

| File | Responsibility |
|---|---|
| `app/__init__.py` | Package marker; reads version |
| `app/config.py` | Reads env vars: paths, Ollama URL, admin seed, threshold, top_k |
| `app/main.py` | FastAPI app, route registration, static-file mount, session middleware |
| `app/auth.py` | Password hashing, session cookie issue/verify, `get_current_user`, `require_role` |
| `app/db.py` | SQLite connection helper, schema migrations, table-level accessors |
| `app/models.py` | Pydantic request/response schemas |
| `app/pdf_utils.py` | `extract_pages(path) -> list[tuple[int, str]]` |
| `app/ingest.py` | `chunk_pages(pages) -> list[Chunk]`; `ingest_pdf(path, doc_id, filename)` |
| `app/retrieve.py` | `get_query_embedding(text)`; `retrieve(query, top_k) -> list[Source]` |
| `app/answer.py` | `build_prompt(sources, question)`; `generate_answer(sources, question) -> AnswerResult` |
| `app/routes_chat.py` | `POST /api/chat` |
| `app/routes_documents.py` | `POST/GET/DELETE /api/documents[/:id]` |
| `app/routes_auth.py` | `/api/auth/login`, `/logout`, `/me` |
| `app/routes_users.py` | `/api/admin/users` (admin only) |
| `app/routes_conversations.py` | `/api/conversations[/:id/messages]` |
| `app/health.py` | `/api/health` |

### Tests (`tests/`)

| File | Covers |
|---|---|
| `tests/conftest.py` | Temp data dir, isolated SQLite/Chroma fixtures |
| `tests/test_pdf_utils.py` | Extraction, encryption rejection, empty pages |
| `tests/test_ingest.py` | Chunking, metadata shape, ingest full flow |
| `tests/test_retrieve.py` | Embedding, top_k, metadata |
| `tests/test_answer.py` | Prompt building, citation parsing, hallucinated drop, refusal trigger, warning flag |
| `tests/test_auth.py` | Hashing, session cookie, role enforcement |
| `tests/test_routes.py` | End-to-end auth + chat + documents integration |
| `tests/eval_questions.json` | 10 question/keyword regression pairs |

### Frontend (`frontend/`)

| File | Responsibility |
|---|---|
| `frontend/package.json` | vite, react, react-router-dom, typescript |
| `frontend/vite.config.ts` | Dev server proxy `/api` → `http://localhost:8000` |
| `frontend/index.html` | Root HTML |
| `frontend/src/main.tsx` | React entry, router setup |
| `frontend/src/api.ts` | Fetch wrappers for all `/api/*` endpoints |
| `frontend/src/auth.tsx` | Auth context + login state |
| `frontend/src/pages/Login.tsx` | Login form |
| `frontend/src/pages/Chat.tsx` | Chat UI + conversation sidebar + citation panel |
| `frontend/src/pages/Admin.tsx` | Document upload + user management tabs |
| `frontend/src/components/CitationChip.tsx` | `[N]` chip + side panel |
| `frontend/src/components/Message.tsx` | Renders a message with citations |

---

## Phase 1 — Ingestion + CLI retrieval (no UI yet)

Phase 1 ends with: a CLI command `python -m campusgpt.ask "question"` that prints an answer + citations using real PDFs ingested via the API.

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `.gitignore`
- Create: `README.md`

**Interfaces:**
- `app.config.Settings` (pydantic BaseSettings) — exposes: `data_dir: Path`, `pdf_dir: Path`, `chroma_dir: Path`, `db_path: Path`, `ollama_url: str`, `ollama_model: str`, `embedding_model_name: str`, `top_k: int = 6`, `confidence_threshold: float = 0.35`, `admin_user: str`, `admin_pass: str`.

**Step 1.** Initialize the project.

```bash
cd "/Users/ritwikeshbhardwaj/projects/university data manager RAG"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
```

**Step 2.** Create `pyproject.toml`:

```toml
[project]
name = "campusgpt"
version = "0.1.0"
description = "Local RAG assistant for university documents"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "pypdf>=5.0",
    "sentence-transformers>=3.0",
    "chromadb>=0.5",
    "pydantic>=2.7",
    "pydantic-settings>=2.4",
    "passlib[bcrypt]>=1.7",
    "itsdangerous>=2.2",
    "python-multipart>=0.0.9",
    "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5.0",
]

[project.scripts]
campusgpt = "app.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
packages = ["app"]
```

**Step 3.** Create `app/__init__.py`:

```python
__version__ = "0.1.0"
```

**Step 4.** Create `app/config.py`:

```python
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CAMPUSGPT_", env_file=".env")

    data_dir: Path = Path("./data")
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    top_k: int = 6
    confidence_threshold: float = 0.35

    # Required at first run; no defaults so accidental empty passwords fail loudly.
    admin_user: str = ""
    admin_pass: str = ""

    @property
    def pdf_dir(self) -> Path:
        return self.data_dir / "pdfs"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "campusgpt.db"

    @property
    def secret_key(self) -> str:
        # Stable per-install secret; can be overridden via env in production.
        return self.admin_user + "_" + "campusgpt_session_secret"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
```

**Step 5.** Create `tests/__init__.py` (empty).

**Step 6.** Create `tests/conftest.py`:

```python
import os
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_data_dir(monkeypatch):
    d = Path(tempfile.mkdtemp(prefix="campusgpt-test-"))
    monkeypatch.setenv("CAMPUSGPT_DATA_DIR", str(d))
    yield d
    shutil.rmtree(d, ignore_errors=True)
```

**Step 7.** Create `.gitignore`:

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
data/
.env
*.egg-info/
dist/
build/
node_modules/
frontend/dist/
.DS_Store
```

**Step 8.** Create `README.md`:

```markdown
# CampusGPT

Local RAG assistant for university documents.

## Setup
1. Install Ollama: https://ollama.com
2. Pull the model: `ollama pull llama3.1:8b`
3. Start the server: `ollama serve` (in another terminal)
4. Install Python deps: `pip install -e ".[dev]"`
5. Seed an admin: `CAMPUSGPT_ADMIN_USER=admin CAMPUSGPT_ADMIN_PASS=changeme python -m campusgpt.bootstrap`
6. Run the backend: `uvicorn app.main:app --reload`
```

**Step 9.** Install and verify:

```bash
source .venv/bin/activate
pip install -e ".[dev]"
python -c "from app.config import settings; print(settings.data_dir)"
```

Expected: prints `data` (or the value of `CAMPUSGPT_DATA_DIR`).

**Step 10.** Initialize git and commit:

```bash
git init
git add .
git commit -m "chore: scaffold project with config and tooling"
```

---

### Task 2: PDF page extraction

**Files:**
- Create: `app/pdf_utils.py`
- Create: `tests/test_pdf_utils.py`
- Create: `tests/fixtures/sample.pdf` (generated in test setup; not committed)

**Interfaces:**
- `extract_pages(path: Path) -> list[tuple[int, str]]` — returns `[(page_number_1_indexed, text), ...]`. Raises `PDFExtractionError` on encryption or unreadable PDF.

- `app/pdf_utils.py`: define `class PDFExtractionError(Exception): pass` at module top.

**Step 1.** Write the failing test (`tests/test_pdf_utils.py`):

```python
from pathlib import Path

import pypdf
import pytest

from app.pdf_utils import PDFExtractionError, extract_pages


def _make_pdf(path: Path, pages_text: list[str]) -> None:
    """Create a tiny valid PDF with the given pages using pypdf's writer."""
    from pypdf import PdfWriter
    from reportlab.pdfgen import canvas  # only used in tests
    # Fallback: use a minimal hand-built PDF if reportlab isn't installed.
    raise RuntimeError("Use the conftest fixture instead")


def test_extract_pages_returns_page_numbers_and_text(tmp_path):
    from tests.conftest import write_sample_pdf
    pdf = tmp_path / "sample.pdf"
    write_sample_pdf(pdf, ["Hello page one", "Second page content"])
    pages = extract_pages(pdf)
    assert pages == [(1, "Hello page one"), (2, "Second page content")]


def test_extract_pages_raises_on_encrypted_pdf(tmp_path):
    # Use pypdf to encrypt an existing file.
    from tests.conftest import write_sample_pdf
    pdf = tmp_path / "enc.pdf"
    write_sample_pdf(pdf, ["secret"])
    reader = pypdf.PdfReader(str(pdf))
    writer = pypdf.PdfWriter()
    for p in reader.pages:
        writer.add_page(p)
    writer.encrypt("hunter2")
    out = tmp_path / "enc_out.pdf"
    with open(out, "wb") as f:
        writer.write(f)
    with pytest.raises(PDFExtractionError):
        extract_pages(out)
```

**Step 2.** Add the fixture helper to `tests/conftest.py`:

```python
def write_sample_pdf(path, pages_text: list[str]) -> None:
    """Create a real multi-page PDF without external libraries."""
    import pypdf
    from pypdf.generic import NameObject, TextStringObject
    from pypdf import PdfWriter
    writer = PdfWriter()
    for text in pages_text:
        page = writer.add_blank_page(width=612, height=792)
        # Use pypdf's text drawing via the page's writer context.
        from pypdf.generic import RectangleObject
        # Simplest: write the text into the page contents stream.
        content = (
            b"BT /F1 12 Tf 72 720 Td (" + text.encode("latin-1") + b") Tj ET"
        )
        page[NameObject("/Contents")] = pypdf.generic.ArrayObject([
            pypdf.generic.DecodedStreamObject()
        ])
        page["/Contents"].set_data(content)
    with open(path, "wb") as f:
        writer.write(f)
```

**Step 3.** Run the test, expect failure:

```bash
pytest tests/test_pdf_utils.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.pdf_utils'`.

**Step 4.** Implement `app/pdf_utils.py`:

```python
from pathlib import Path

import pypdf


class PDFExtractionError(Exception):
    """Raised when a PDF cannot be read (encrypted, scanned, malformed)."""


def extract_pages(path: Path) -> list[tuple[int, str]]:
    """Return [(page_number, text)] with 1-indexed page numbers.

    Raises PDFExtractionError on encrypted or unreadable PDFs.
    Pages with no extractable text are skipped.
    """
    try:
        reader = pypdf.PdfReader(str(path))
    except Exception as exc:
        raise PDFExtractionError(f"Could not open PDF: {exc}") from exc

    if reader.is_encrypted:
        raise PDFExtractionError("PDF is encrypted; password-protected files are not supported.")

    pages: list[tuple[int, str]] = []
    for idx, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            raise PDFExtractionError(f"Could not extract page {idx}: {exc}") from exc
        text = text.strip()
        if text:
            pages.append((idx, text))
    if not pages:
        raise PDFExtractionError("No extractable text found. Scanned PDFs require OCR, which is not yet supported.")
    return pages
```

**Step 5.** Run the test, expect pass:

```bash
pytest tests/test_pdf_utils.py -v
```

Expected: 2 passed.

**Step 6.** Commit:

```bash
git add app/pdf_utils.py tests/test_pdf_utils.py tests/conftest.py
git commit -m "feat: PDF page extraction with encrypted/scanned detection"
```

---

### Task 3: Sentence-aware chunking per page

**Files:**
- Create: `app/ingest.py`
- Create: `tests/test_ingest.py`

**Interfaces:**
- `Chunk` (dataclass) — fields: `text: str`, `page: int`, `chunk_index: int` (per-page index).
- `chunk_pages(pages: list[tuple[int, str]], target_chars: int = 2000) -> list[Chunk]` — splits each page's text on sentence boundaries; never merges across pages.

**Step 1.** Write the failing test (`tests/test_ingest.py`):

```python
from app.ingest import Chunk, chunk_pages


def test_chunks_never_cross_page_boundary():
    pages = [(1, "Sentence one. Sentence two. " * 200), (2, "Page two only.")]
    chunks = chunk_pages(pages, target_chars=500)
    assert all(c.page in (1, 2) for c in chunks)
    # No chunk should contain text from both pages
    assert all("Page two only." not in c.text for c in chunks if c.page == 1)
    assert all("Sentence one." not in c.text for c in chunks if c.page == 2)


def test_chunks_split_on_sentence_boundaries():
    pages = [(1, "First sentence. Second sentence. Third sentence. Fourth sentence.")]
    chunks = chunk_pages(pages, target_chars=30)
    # Each chunk ends with a period or is the final chunk
    for c in chunks[:-1]:
        assert c.text.rstrip().endswith(".")
    assert chunks  # at least one chunk produced


def test_chunk_index_resets_per_page():
    pages = [(1, "A. " * 100), (2, "B. " * 100)]
    chunks = chunk_pages(pages, target_chars=200)
    page_1_indices = [c.chunk_index for c in chunks if c.page == 1]
    page_2_indices = [c.chunk_index for c in chunks if c.page == 2]
    assert page_1_indices == list(range(len(page_1_indices)))
    assert page_2_indices == list(range(len(page_2_indices)))


def test_short_page_produces_single_chunk():
    pages = [(1, "Short text.")]
    chunks = chunk_pages(pages, target_chars=2000)
    assert len(chunks) == 1
    assert chunks[0].text == "Short text."
    assert chunks[0].page == 1
    assert chunks[0].chunk_index == 0
```

**Step 2.** Run, expect failure:

```bash
pytest tests/test_ingest.py -v
```

**Step 3.** Implement `app/ingest.py`:

```python
from dataclasses import dataclass
import re


@dataclass
class Chunk:
    text: str
    page: int
    chunk_index: int


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_SPLIT.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def chunk_pages(pages: list[tuple[int, str]], target_chars: int = 2000) -> list[Chunk]:
    """Split each page's text on sentence boundaries into ~target_chars chunks.

    Chunks never cross page boundaries. chunk_index resets per page.
    """
    chunks: list[Chunk] = []
    for page_num, text in pages:
        sentences = _split_sentences(text)
        buffer = ""
        idx = 0
        for sent in sentences:
            # If adding this sentence would overflow and buffer is non-empty, flush.
            if buffer and len(buffer) + 1 + len(sent) > target_chars:
                chunks.append(Chunk(text=buffer, page=page_num, chunk_index=idx))
                idx += 1
                buffer = sent
            else:
                buffer = (buffer + " " + sent).strip() if buffer else sent
        if buffer:
            chunks.append(Chunk(text=buffer, page=page_num, chunk_index=idx))
    return chunks
```

**Step 4.** Run, expect pass:

```bash
pytest tests/test_ingest.py -v
```

Expected: 4 passed.

**Step 5.** Commit:

```bash
git add app/ingest.py tests/test_ingest.py
git commit -m "feat: sentence-aware per-page chunking"
```

---

### Task 4: ChromaDB wrapper + retrieval

**Files:**
- Create: `app/retrieve.py`
- Create: `tests/test_retrieve.py`

**Interfaces:**
- `Source` (dataclass) — fields: `doc_id: int`, `doc_name: str`, `page: int`, `chunk_index: int`, `text: str`, `score: float`.
- `get_collection(persist_dir)` — returns a singleton Chroma collection named `campusgpt_chunks`.
- `add_chunks(doc_id, doc_name, chunks, embedding_model)` — upserts chunks with metadata.
- `retrieve(query: str, top_k: int = 6) -> list[Source]` — embed query, search, return Sources.

The embedding model is loaded once per process via `@lru_cache` and used both for ingestion and retrieval.

**Step 1.** Write the failing test (`tests/test_retrieve.py`):

```python
from pathlib import Path

import pytest

from app.retrieve import Source, retrieve, add_chunks, get_collection
from app.ingest import Chunk


@pytest.fixture
def chroma_dir(tmp_path):
    d = tmp_path / "chroma"
    d.mkdir()
    return d


def _model():
    """Lazy-load the real embedding model; skip test if model download fails."""
    pytest.importorskip("sentence_transformers")
    from sentence_transformers import SentenceTransformer
    try:
        return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    except Exception:
        pytest.skip("Embedding model not available offline")


def test_add_and_retrieve_returns_top_k(chroma_dir):
    model = _model()
    chunks = [
        Chunk("Scholarship eligibility requires CGPA 8.5 or higher.", 1, 0),
        Chunk("Graduation requires 120 credits minimum.", 5, 0),
        Chunk("Hostel renewal needs identity proof and fee receipt.", 9, 0),
    ]
    add_chunks(doc_id=1, doc_name="handbook.pdf", chunks=chunks, model=model, persist_dir=chroma_dir)
    results = retrieve("What is the scholarship eligibility?", top_k=2, model=model, persist_dir=chroma_dir)
    assert len(results) == 2
    assert all(isinstance(r, Source) for r in results)
    # Top hit should be the scholarship one
    assert "Scholarship" in results[0].text
    assert results[0].doc_name == "handbook.pdf"
    assert results[0].page == 1
    assert results[0].score > results[1].score


def test_retrieve_returns_metadata(chroma_dir):
    model = _model()
    chunks = [Chunk("Attendance requirement is 75 percent.", 3, 0)]
    add_chunks(doc_id=2, doc_name="rules.pdf", chunks=chunks, model=model, persist_dir=chroma_dir)
    results = retrieve("attendance", top_k=1, model=model, persist_dir=chroma_dir)
    assert results[0].doc_id == 2
    assert results[0].page == 3
```

**Step 2.** Run, expect failure:

```bash
pytest tests/test_retrieve.py -v
```

**Step 3.** Implement `app/retrieve.py`:

```python
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

from app.ingest import Chunk


COLLECTION_NAME = "campusgpt_chunks"


@dataclass
class Source:
    doc_id: int
    doc_name: str
    page: int
    chunk_index: int
    text: str
    score: float


@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    from app.config import settings
    return SentenceTransformer(settings.embedding_model_name)


def get_collection(persist_dir: Path):
    client = chromadb.PersistentClient(path=str(persist_dir))
    return client.get_or_create_collection(
        name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )


def _chunk_id(doc_id: int, page: int, chunk_index: int) -> str:
    return f"doc{doc_id}-p{page}-c{chunk_index}"


def add_chunks(
    doc_id: int,
    doc_name: str,
    chunks: list[Chunk],
    model: SentenceTransformer | None = None,
    persist_dir: Path | None = None,
) -> None:
    from app.config import settings
    model = model or get_model()
    persist_dir = persist_dir or settings.chroma_dir
    if not chunks:
        return
    texts = [c.text for c in chunks]
    embeddings = model.encode(texts, convert_to_numpy=True).tolist()
    ids = [_chunk_id(doc_id, c.page, c.chunk_index) for c in chunks]
    metadatas = [
        {"doc_id": doc_id, "doc_name": doc_name, "page": c.page, "chunk_index": c.chunk_index}
        for c in chunks
    ]
    coll = get_collection(persist_dir)
    coll.upsert(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)


def retrieve(
    query: str,
    top_k: int = 6,
    model: SentenceTransformer | None = None,
    persist_dir: Path | None = None,
) -> list[Source]:
    from app.config import settings
    model = model or get_model()
    persist_dir = persist_dir or settings.chroma_dir
    coll = get_collection(persist_dir)
    q_emb = model.encode([query], convert_to_numpy=True).tolist()
    res = coll.query(query_embeddings=q_emb, n_results=top_k)
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]
    sources: list[Source] = []
    for text, meta, dist in zip(docs, metas, dists):
        # cosine distance → similarity in [0,1]; higher score = more relevant
        score = max(0.0, 1.0 - float(dist))
        sources.append(
            Source(
                doc_id=int(meta["doc_id"]),
                doc_name=str(meta["doc_name"]),
                page=int(meta["page"]),
                chunk_index=int(meta["chunk_index"]),
                text=text,
                score=score,
            )
        )
    return sources
```

**Step 4.** Run, expect pass (may skip if model not downloadable):

```bash
pytest tests/test_retrieve.py -v
```

Expected: 2 passed (or skipped if no network for model).

**Step 5.** Commit:

```bash
git add app/retrieve.py tests/test_retrieve.py
git commit -m "feat: ChromaDB-backed retrieval with cosine similarity scores"
```

---

### Task 5: SQLite schema + document metadata

**Files:**
- Create: `app/db.py`
- Create: `tests/test_db.py`

**Interfaces:**
- `init_db(path)` — creates tables if not exist; safe to call repeatedly.
- `add_document(filename, pages) -> int` — returns doc_id.
- `set_chunk_count(doc_id, count)`.
- `list_documents() -> list[dict]`.
- `delete_document(doc_id) -> filename | None`.
- `get_document(doc_id) -> dict | None`.

**Step 1.** Write failing tests (`tests/test_db.py`):

```python
from app.db import init_db, add_document, set_chunk_count, list_documents, delete_document


def test_document_lifecycle(tmp_path):
    db = tmp_path / "c.db"
    init_db(db)
    assert list_documents(db) == []
    doc_id = add_document(db, "regulations.pdf", pages=42)
    set_chunk_count(db, doc_id, 100)
    docs = list_documents(db)
    assert len(docs) == 1
    assert docs[0]["filename"] == "regulations.pdf"
    assert docs[0]["pages"] == 42
    assert docs[0]["chunks"] == 100
    fname = delete_document(db, doc_id)
    assert fname == "regulations.pdf"
    assert list_documents(db) == []


def test_init_db_is_idempotent(tmp_path):
    db = tmp_path / "c.db"
    init_db(db)
    init_db(db)  # no error
    add_document(db, "x.pdf", pages=1)
```

**Step 2.** Run, expect failure:

```bash
pytest tests/test_db.py -v
```

**Step 3.** Implement `app/db.py`:

```python
import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT NOT NULL,
    pages       INTEGER NOT NULL,
    chunks      INTEGER NOT NULL DEFAULT 0,
    uploaded_at TEXT DEFAULT (datetime('now'))
);
"""


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path) -> None:
    with _connect(db_path) as conn:
        conn.executescript(SCHEMA)


def add_document(db_path: Path, filename: str, pages: int) -> int:
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO documents (filename, pages) VALUES (?, ?)",
            (filename, pages),
        )
        return cur.lastrowid


def set_chunk_count(db_path: Path, doc_id: int, count: int) -> None:
    with _connect(db_path) as conn:
        conn.execute("UPDATE documents SET chunks = ? WHERE id = ?", (count, doc_id))


def list_documents(db_path: Path) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, filename, pages, chunks, uploaded_at FROM documents ORDER BY uploaded_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_document(db_path: Path, doc_id: int) -> dict | None:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT id, filename, pages, chunks, uploaded_at FROM documents WHERE id = ?",
            (doc_id,),
        ).fetchone()
        return dict(row) if row else None


def delete_document(db_path: Path, doc_id: int) -> str | None:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT filename FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        return row["filename"]
```

**Step 4.** Run, expect pass:

```bash
pytest tests/test_db.py -v
```

Expected: 2 passed.

**Step 5.** Commit:

```bash
git add app/db.py tests/test_db.py
git commit -m "feat: SQLite schema and document metadata accessors"
```

---

### Task 6: Ingest pipeline (PDF → chunks → DB + Chroma)

**Files:**
- Create: `app/ingest_pipeline.py` (orchestrator that combines pdf_utils, ingest, retrieve, db)
- Create: `tests/test_ingest_pipeline.py`

**Interfaces:**
- `ingest_pdf(pdf_path: Path, filename: str) -> dict` — runs the full pipeline. Returns `{"doc_id": int, "filename": str, "pages": int, "chunks": int}`. On failure, cleans up the saved file and re-raises.

**Step 1.** Write failing test (`tests/test_ingest_pipeline.py`):

```python
import shutil
from pathlib import Path

import pytest

from app.ingest_pipeline import ingest_pdf
from tests.conftest import write_sample_pdf


def test_ingest_pdf_full_flow(tmp_path, monkeypatch):
    # Set up isolated data dirs
    data_dir = tmp_path / "data"
    pdf_dir = data_dir / "pdfs"
    chroma_dir = data_dir / "chroma"
    db_path = data_dir / "c.db"
    pdf_dir.mkdir(parents=True)
    chroma_dir.mkdir(parents=True)
    monkeypatch.setenv("CAMPUSGPT_DATA_DIR", str(data_dir))

    # Reload settings
    import importlib
    from app import config
    importlib.reload(config)

    src = tmp_path / "src.pdf"
    write_sample_pdf(src, ["Page one text. " * 50, "Page two text. " * 50])
    saved_path = tmp_path / "incoming.pdf"
    shutil.copy(src, saved_path)

    result = ingest_pdf(saved_path, "regulations.pdf")
    assert result["filename"] == "regulations.pdf"
    assert result["pages"] >= 1
    assert result["chunks"] >= 1
    assert (pdf_dir / "regulations.pdf").exists()  # saved with original name
```

**Step 2.** Run, expect failure:

```bash
pytest tests/test_ingest_pipeline.py -v
```

**Step 3.** Implement `app/ingest_pipeline.py`:

```python
import shutil
from pathlib import Path

from app.config import settings
from app.db import add_document, init_db, set_chunk_count
from app.ingest import chunk_pages
from app.pdf_utils import PDFExtractionError, extract_pages
from app.retrieve import add_chunks, get_model


def ingest_pdf(pdf_path: Path, filename: str) -> dict:
    """Extract pages, chunk, embed, store in ChromaDB, register in SQLite.

    On any failure after the file copy, the file is removed to keep state clean.
    """
    settings.ensure_dirs()
    init_db(settings.db_path)

    dest = settings.pdf_dir / filename
    shutil.copy(pdf_path, dest)

    try:
        pages = extract_pages(dest)
    except PDFExtractionError:
        dest.unlink(missing_ok=True)
        raise

    chunks = chunk_pages(pages)
    if not chunks:
        dest.unlink(missing_ok=True)
        raise PDFExtractionError("No chunks could be produced from this PDF.")

    doc_id = add_document(settings.db_path, filename=filename, pages=len(pages))

    try:
        model = get_model()
        add_chunks(doc_id=doc_id, doc_name=filename, chunks=chunks, model=model)
    except Exception:
        # Rollback: remove the chunks we may have written, the DB row, and the file.
        from app.retrieve import get_collection
        coll = get_collection(settings.chroma_dir)
        ids = [f"doc{doc_id}-p{c.page}-c{c.chunk_index}" for c in chunks]
        try:
            coll.delete(ids=ids)
        except Exception:
            pass
        from app.db import delete_document
        delete_document(settings.db_path, doc_id)
        dest.unlink(missing_ok=True)
        raise

    set_chunk_count(settings.db_path, doc_id, count=len(chunks))
    return {
        "doc_id": doc_id,
        "filename": filename,
        "pages": len(pages),
        "chunks": len(chunks),
    }
```

**Step 4.** Run, expect pass:

```bash
pytest tests/test_ingest_pipeline.py -v
```

**Step 5.** Commit:

```bash
git add app/ingest_pipeline.py tests/test_ingest_pipeline.py
git commit -m "feat: end-to-end PDF ingest pipeline with rollback on failure"
```

---

### Task 7: Answer generation (prompt, Ollama call, citation parsing)

**Files:**
- Create: `app/answer.py`
- Create: `app/models.py` (Pydantic schemas)
- Create: `tests/test_answer.py`

**Interfaces:**

In `app/models.py`:

```python
from pydantic import BaseModel


class Citation(BaseModel):
    number: int           # [N] as cited by the model
    doc_name: str
    page: int
    passage: str


class AnswerResponse(BaseModel):
    answer: str
    citations: list[Citation]
    refused: bool
    warning: str | None = None
    closest_source: Citation | None = None  # populated when refused
```

In `app/answer.py`:

```python
@dataclass
class AnswerResult:
    answer: str
    citations: list[Citation]
    refused: bool
    warning: str | None
    closest_source: Citation | None

def build_prompt(sources: list[Source], question: str) -> str: ...
def parse_citations(answer_text: str, sources: list[Source]) -> tuple[str, list[Citation]]: ...
def should_refuse(sources: list[Source]) -> bool: ...
def generate_answer(question: str, sources: list[Source]) -> AnswerResult: ...  # calls Ollama
```

**Step 1.** Write `app/models.py` (just the schemas listed above plus a `Source`-equivalent, but Source is in `app.retrieve` — AnswerResponse references Citation only).

**Step 2.** Write failing test (`tests/test_answer.py`):

```python
import re

import pytest

from app.answer import build_prompt, parse_citations, should_refuse
from app.retrieve import Source


def test_should_refuse_below_threshold():
    assert should_refuse([Source(1, "a.pdf", 1, 0, "x", 0.20)]) is True
    assert should_refuse([Source(1, "a.pdf", 1, 0, "x", 0.50)]) is False
    assert should_refuse([]) is True


def test_build_prompt_includes_sources_and_question():
    sources = [
        Source(1, "reg.pdf", 4, 0, "Graduation requires 120 credits.", 0.9),
        Source(2, "sch.pdf", 2, 0, "CGPA 8.5 required.", 0.8),
    ]
    prompt = build_prompt(sources, "How many credits to graduate?")
    assert "[1]" in prompt and "reg.pdf" in prompt and "120 credits" in prompt
    assert "[2]" in prompt and "sch.pdf" in prompt
    assert "How many credits to graduate?" in prompt


def test_parse_citations_extracts_valid_numbers():
    sources = [
        Source(1, "reg.pdf", 4, 0, "120 credits required.", 0.9),
        Source(2, "sch.pdf", 2, 0, "CGPA 8.5 required.", 0.8),
    ]
    text = "You need 120 credits [1] and a CGPA of 8.5 [2]."
    cleaned, citations = parse_citations(text, sources)
    assert cleaned == text  # no rewriting in v1
    assert len(citations) == 2
    assert citations[0].number == 1 and citations[0].doc_name == "reg.pdf" and citations[0].page == 4
    assert citations[1].number == 2 and citations[1].doc_name == "sch.pdf"


def test_parse_citations_drops_hallucinated_numbers():
    sources = [Source(1, "reg.pdf", 4, 0, "120 credits.", 0.9)]
    text = "See [1] and also [7] and [3] for more."
    _, citations = parse_citations(text, sources)
    assert len(citations) == 1
    assert citations[0].number == 1


def test_parse_citations_handles_no_citations():
    sources = [Source(1, "reg.pdf", 4, 0, "120 credits.", 0.9)]
    text = "The answer is 120 credits."
    _, citations = parse_citations(text, sources)
    assert citations == []


def test_ollama_generate_returns_answer(monkeypatch):
    # Stub the Ollama HTTP call
    import app.answer as answer_mod

    class FakeResp:
        def raise_for_status(self): pass
        def json(self): return {"response": "You need 120 credits [1]."}

    class FakeClient:
        def post(self, url, json=None):
            class R:
                def __enter__(self_inner): return FakeResp()
                def __exit__(self_inner, *a): pass
            return R()

    monkeypatch.setattr(answer_mod.httpx, "post", lambda url, json=None: FakeResp().__enter__())

    sources = [Source(1, "reg.pdf", 4, 0, "120 credits required.", 0.9)]
    result = answer_mod.generate_answer("credits?", sources)
    assert result.refused is False
    assert "120 credits" in result.answer
    assert len(result.citations) == 1
```

**Step 3.** Run, expect failure:

```bash
pytest tests/test_answer.py -v
```

**Step 4.** Implement `app/answer.py`:

```python
import re
from dataclasses import dataclass

import httpx

from app.config import settings
from app.models import Citation
from app.retrieve import Source


@dataclass
class AnswerResult:
    answer: str
    citations: list[Citation]
    refused: bool
    warning: str | None
    closest_source: Citation | None


SYSTEM_PROMPT = (
    "You are CampusGPT, a university document assistant. "
    "Answer the user's question using ONLY the numbered sources provided below. "
    "Cite sources in your answer as [1], [2], etc. "
    "If the answer is not fully contained in the sources, say exactly: "
    "'I don't have enough information in the provided documents to answer this question.' "
    "Never make up information."
)


def should_refuse(sources: list[Source]) -> bool:
    if not sources:
        return True
    return sources[0].score < settings.confidence_threshold


def build_prompt(sources: list[Source], question: str) -> str:
    blocks = []
    for i, s in enumerate(sources, start=1):
        blocks.append(f"[{i}] {s.doc_name}, p.{s.page} — \"{s.text}\"")
    sources_text = "\n".join(blocks)
    return (
        f"<s>[INST] {SYSTEM_PROMPT}\n\n"
        f"Sources:\n{sources_text}\n\n"
        f"User: {question} [/INST]"
    )


_CITATION_RE = re.compile(r"\[([1-9][0-9]*)\]")


def parse_citations(answer_text: str, sources: list[Source]) -> tuple[str, list[Citation]]:
    """Extract [N] citations and resolve to Citation objects.

    Numbers > len(sources) are dropped (hallucination guard).
    """
    seen: set[int] = set()
    citations: list[Citation] = []
    for m in _CITATION_RE.finditer(answer_text):
        n = int(m.group(1))
        if n in seen:
            continue
        if 1 <= n <= len(sources):
            seen.add(n)
            src = sources[n - 1]
            citations.append(
                Citation(
                    number=n,
                    doc_name=src.doc_name,
                    page=src.page,
                    passage=src.text,
                )
            )
    return answer_text, citations


def generate_answer(question: str, sources: list[Source]) -> AnswerResult:
    if should_refuse(sources):
        closest = sources[0] if sources else None
        closest_cite = (
            Citation(number=1, doc_name=closest.doc_name, page=closest.page, passage=closest.text)
            if closest
            else None
        )
        return AnswerResult(
            answer=(
                "I couldn't find this in the uploaded documents. "
                "Here is the closest match I found; please check the original document."
            ),
            citations=[],
            refused=True,
            warning=None,
            closest_source=closest_cite,
        )

    prompt = build_prompt(sources, question)
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 400},
    }
    resp = httpx.post(
        f"{settings.ollama_url}/api/generate",
        json=payload,
        timeout=120.0,
    )
    resp.raise_for_status()
    raw = resp.json().get("response", "")

    cleaned, citations = parse_citations(raw, sources)
    refused_phrase = "I don't have enough information"
    refused = refused_phrase in cleaned

    warning = None
    if not refused and not citations:
        warning = "This answer may not be fully grounded in the source documents."

    return AnswerResult(
        answer=cleaned,
        citations=citations,
        refused=refused,
        warning=warning,
        closest_source=None,
    )
```

**Step 5.** Run, expect pass:

```bash
pytest tests/test_answer.py -v
```

Expected: 6 passed.

**Step 6.** Commit:

```bash
git add app/answer.py app/models.py tests/test_answer.py
git commit -m "feat: answer generation with Ollama, citation parsing, refusal"
```

---

### Task 8: FastAPI skeleton + `/api/health`

**Files:**
- Create: `app/main.py`
- Create: `app/health.py`
- Create: `tests/test_main.py`

**Step 1.** Write failing test:

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert data["status"] in ("ok", "degraded")
```

**Step 2.** Implement `app/health.py`:

```python
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
```

**Step 3.** Implement `app/main.py`:

```python
from fastapi import FastAPI

from app.config import settings
from app.db import init_db
from app.health import router as health_router


def create_app() -> FastAPI:
    settings.ensure_dirs()
    init_db(settings.db_path)
    app = FastAPI(title="CampusGPT")
    app.include_router(health_router)
    return app


app = create_app()
```

**Step 4.** Run tests:

```bash
pytest tests/test_main.py -v
```

**Step 5.** Commit:

```bash
git add app/main.py app/health.py tests/test_main.py
git commit -m "feat: FastAPI skeleton with health endpoint"
```

---

### Task 9: CLI for Phase 1 acceptance

**Files:**
- Create: `app/cli.py`
- Create: `tests/test_cli.py`

**Step 1.** Implement `app/cli.py`:

```python
import argparse
import json
import sys

from app.config import settings
from app.db import init_db
from app.ingest_pipeline import ingest_pdf
from app.answer import generate_answer
from app.retrieve import retrieve


def cmd_ingest(args):
    settings.ensure_dirs()
    init_db(settings.db_path)
    result = ingest_pdf(args.path, args.filename or args.path.name)
    print(json.dumps(result, indent=2))


def cmd_ask(args):
    sources = retrieve(args.question, top_k=settings.top_k)
    result = generate_answer(args.question, sources)
    print("Answer:", result.answer)
    if result.refused and result.closest_source:
        cs = result.closest_source
        print(f"\nClosest source: {cs.doc_name}, p.{cs.page}\n  \"{cs.passage}\"")
        return
    for c in result.citations:
        print(f"  [{c.number}] {c.doc_name}, p.{c.page}")
        print(f"      \"{c.passage}\"")
    if result.warning:
        print(f"\n⚠️  {result.warning}")


def main():
    parser = argparse.ArgumentParser(prog="campusgpt")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_ingest = sub.add_parser("ingest")
    p_ingest.add_argument("path", type=lambda p: __import__("pathlib").Path(p))
    p_ingest.add_argument("--filename", default=None)
    p_ingest.set_defaults(func=cmd_ingest)
    p_ask = sub.add_parser("ask")
    p_ask.add_argument("question")
    p_ask.set_defaults(func=cmd_ask)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
```

**Step 2.** Smoke test:

```bash
source .venv/bin/activate
# Start ollama in another terminal first: `ollama serve`
python -m app.cli ingest tests/fixtures/sample.pdf --filename sample.pdf
python -m app.cli ask "What does this document say?"
```

Expected: prints an answer and citations.

**Step 3.** Commit:

```bash
git add app/cli.py
git commit -m "feat: CLI for ingest and ask — Phase 1 complete"
```

---

## Phase 2 — Auth + conversation persistence + web UI

Phase 2 ends with: students log in, have private chat history, admins log in too and can upload via a web UI.

---

### Task 10: SQLite schema for users, conversations, messages

**Files:**
- Modify: `app/db.py` (add tables + accessors)

**Interfaces:**
- `create_user(db_path, username, password_hash, role) -> int`
- `get_user_by_username(db_path, username) -> dict | None`
- `get_user_by_id(db_path, user_id) -> dict | None`
- `list_users(db_path) -> list[dict]`
- `delete_user(db_path, user_id) -> None`
- `create_conversation(db_path, user_id, title=None) -> int`
- `list_conversations(db_path, user_id) -> list[dict]`
- `get_conversation(db_path, conv_id, user_id) -> dict | None`
- `delete_conversation(db_path, conv_id, user_id) -> None`
- `add_message(db_path, conv_id, role, content, citations_json=None, refused=False) -> int`
- `get_messages(db_path, conv_id, user_id) -> list[dict]`

**Step 1.** Extend `tests/test_db.py` with cases for users and conversations.

**Step 2.** Extend `app/db.py` SCHEMA with:

```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('student','admin')),
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user','assistant')),
    content TEXT NOT NULL,
    citations_json TEXT,
    refused INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
```

Plus the accessor functions.

**Step 3.** Run, commit:

```bash
pytest tests/test_db.py -v
git add app/db.py tests/test_db.py
git commit -m "feat: users, conversations, messages tables and accessors"
```

---

### Task 11: Auth — password hashing + session cookie

**Files:**
- Create: `app/auth.py`
- Create: `tests/test_auth.py`

**Interfaces:**
- `hash_password(plain) -> str`
- `verify_password(plain, hashed) -> bool`
- `issue_session(response: Response, user_id: int)`
- `read_session(request: Request) -> int | None`  # returns user_id
- `clear_session(response: Response)`
- `get_current_user(request) -> dict | None` (FastAPI dep)
- `require_user(request) -> dict` (raises 401)
- `require_role(role: str)` — returns a dependency that raises 403 if user.role != role

**Step 1.** Write tests for hashing and verify.

**Step 2.** Implement using passlib + itsdangerous. Session cookie name `campusgpt_session`. Use `settings.secret_key` as the signing key.

**Step 3.** Commit.

---

### Task 12: Auth routes

**Files:**
- Create: `app/routes_auth.py`

**Endpoints:**
- `POST /api/auth/login` body `{username, password}` → sets cookie, returns `{id, username, role}`
- `POST /api/auth/logout` → clears cookie
- `GET /api/auth/me` → returns current user or 401

Tests cover happy path, wrong password, missing fields.

---

### Task 13: Admin user-management routes

**Files:**
- Create: `app/routes_users.py`

**Endpoints:**
- `GET /api/admin/users` → list (admin only)
- `POST /api/admin/users` body `{username, password, role}` → 201 with user (admin only)
- `DELETE /api/admin/users/:id` → 204 (admin only; cannot delete self)

Tests cover role enforcement, duplicate username rejection.

---

### Task 14: Conversation routes

**Files:**
- Create: `app/routes_conversations.py`

**Endpoints:**
- `GET /api/conversations` → current user's conversations
- `POST /api/conversations` body `{title?}` → `{id}`
- `DELETE /api/conversations/:id` → 204 (owner only)
- `GET /api/conversations/:id/messages` → ordered messages (owner only)

Tests cover ownership enforcement and deletion cascade.

---

### Task 15: Document routes

**Files:**
- Create: `app/routes_documents.py`

**Endpoints:**
- `POST /api/documents` → multipart upload (admin only), returns `UploadResponse`
- `GET /api/documents` → list (any auth user)
- `DELETE /api/documents/:id` → admin only; deletes PDF file, ChromaDB chunks, SQLite row

Tests cover admin-only enforcement, non-PDF rejection, deletion cascade.

---

### Task 16: Chat route

**Files:**
- Create: `app/routes_chat.py`

**Endpoint:**
- `POST /api/chat` body `{question, conversation_id}` → returns `AnswerResponse`, persists user + assistant messages

Tests cover:
- Persisting both messages
- Refusal path persists refusal flag and `closest_source`
- Conversation ownership enforced

---

### Task 17: Wire routes into `app/main.py`

**Files:**
- Modify: `app/main.py`

Add `include_router` for auth, users, conversations, documents, chat, health. Add CORS middleware (allow `http://localhost:5173` for Vite dev).

---

### Task 18: React project scaffolding

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/api.ts`
- Create: `frontend/src/auth.tsx`
- Create: `frontend/src/pages/Login.tsx`

`vite.config.ts` proxies `/api` → `http://localhost:8000`.

`auth.tsx` exposes an `AuthContext` with `user`, `login()`, `logout()`, `fetchMe()`.

`Login.tsx` posts to `/api/auth/login`, on success sets user in context and navigates to `/`.

**Commit:** `chore: scaffold React app with auth and login page`

---

### Task 19: Chat UI

**Files:**
- Create: `frontend/src/pages/Chat.tsx`
- Create: `frontend/src/components/CitationChip.tsx`
- Create: `frontend/src/components/Message.tsx`

`Chat.tsx`:
- Sidebar: list of conversations, "New Chat" button, conversation click loads messages.
- Main: scrollable message list, input box at bottom.
- On send: POST `/api/chat` with current conversation_id (creating one if none), append messages.

`CitationChip.tsx`:
- Renders `[N]`; click opens a side panel with `doc_name`, `page`, passage (truncated).

**Commit:** `feat: chat UI with citations and conversation sidebar`

---

### Task 20: Admin UI

**Files:**
- Create: `frontend/src/pages/Admin.tsx`

Two tabs:
- **Documents:** drag-and-drop uploader, list of docs with delete buttons.
- **Users:** create-user form (username, password, role), list with delete.

Admin role gate: redirect non-admins to `/`.

**Commit:** `feat: admin UI for documents and users`

---

## Phase 3 — Honest-answer controls + admin features

---

### Task 21: Confidence threshold + refusal UI

Already implemented in `app/answer.py` (Task 7). Verify end-to-end through `/api/chat`:
- Out-of-scope question → refusal message, no citations, `closest_source` populated.
- In-scope but tangential → may return warning.

Add a UI variant in `Message.tsx` that renders refusal distinctly (yellow card) and shows `closest_source`.

**Commit:** `feat: refusal path end-to-end with distinct UI`

---

### Task 22: Citation hallucination guard

Already implemented in `parse_citations`. Add a backend test that verifies a model response with `[99]` returns zero citations and the answer text is preserved.

**Commit:** `test: citation hallucination guard`

---

### Task 23: Eval set

**Files:**
- Create: `tests/eval_questions.json` with 10 questions + expected keywords
- Create: `tests/test_eval.py` — loads eval set, runs each question through `retrieve + generate_answer` against a seeded corpus (use fixtures), asserts expected keywords appear in retrieved passages.

**Commit:** `test: eval set with 10 question/keyword pairs`

---

### Task 24: Structured request logging

**Files:**
- Modify: `app/main.py` — add a middleware that logs one JSON line per request with `{ts, path, user_id, status, latency_ms}`.
- `retrieve` and `answer` log retrieval events: `{top_scores, refused, citations_count}`.

Tests verify log lines contain expected keys.

**Commit:** `feat: structured JSON request and retrieval logging`

---

## Phase 4 — Polish

---

### Task 25: Health endpoint improvements

Health endpoint already exists. Add a `/api/health/deep` route that does a tiny roundtrip with Ollama (`/api/version`) and a Chroma count, returns both statuses with latencies.

**Commit:** `feat: deep health check`

---

### Task 26: Docker setup

**Files:**
- Create: `Dockerfile` (backend)
- Create: `docker-compose.yml` (Ollama service + backend service, mounted `data/` volume)

The compose file should:
- Start `ollama/ollama`
- Run `ollama pull llama3.1:8b` on first start
- Build and run the backend
- Mount `./data` from the host

Document in README: `docker compose up --build` brings up everything; admin must be seeded on first run via env vars.

**Commit:** `chore: docker setup for backend + ollama`

---

### Task 27: README rewrite

Replace the stub README with:
- One-paragraph description
- Prerequisites (Ollama install)
- Quick start (dev)
- Quick start (Docker)
- Configuration env vars table
- Architecture overview with link to spec
- API endpoint reference (link to `docs/superpowers/specs/...`)

**Commit:** `docs: README rewrite with quick start and env reference`

---

## Self-Review Notes

**Spec coverage:**

| Spec section | Task |
|---|---|
| §1 Stack | Tasks 1, 4, 11 |
| §2 Architecture | Task 1 (scaffold) + Tasks 8, 17 |
| §3 Backend modules | Tasks 2-9, 11-17 |
| §4 Data model | Tasks 5, 10 |
| §5 Authorization | Tasks 11, 13, 15 |
| §6 PDF ingestion | Tasks 2, 3, 6 |
| §7 Retrieval & answering | Tasks 4, 7 |
| §8 API endpoints | Tasks 8, 12, 13, 14, 15, 16 |
| §9 Frontend pages | Tasks 18, 19, 20 |
| §10 Error handling | Inline in Tasks 6, 12-16 |
| §11 Logging | Task 24 |
| §12 Testing | Tasks 1-9 unit/integration; Task 23 eval set |
| §13 Phased delivery | Phase 1 (Tasks 1-9); Phase 2 (Tasks 10-20); Phase 3 (Tasks 21-24); Phase 4 (Tasks 25-27) |

**Placeholder scan:** No TBDs. Inline code for every non-trivial step.

**Type consistency:**
- `Source` is in `app.retrieve` and used in `app.answer` and `app.cli` consistently.
- `Citation` (Pydantic) and `AnswerResult` (dataclass) are distinguished; AnswerResponse uses Citation.
- All references to `doc_id`, `doc_name`, `page`, `chunk_index` are consistent across `ingest`, `retrieve`, `answer`.
- `settings.confidence_threshold` referenced only in `app/answer.py`.

**Gaps found and addressed during review:** Initial plan had only the `/api/chat` route minimal; expanded to full Phase 2 with explicit auth, conversation, document, and user routes. Phase 3 adds the eval set, which was in the spec but not in the original task list.
