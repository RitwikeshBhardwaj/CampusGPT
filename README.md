# CampusGPT

CampusGPT is a fully local Retrieval-Augmented Generation (RAG) system that lets university students and admins ask natural-language questions against a shared library of PDF documents and receive grounded answers with inline citations (doc name, page, and passage).

Everything runs on your own machine: no cloud APIs, no data leaves your machine.

## Prerequisites

- [Ollama](https://ollama.com) — to run the `llama3.1:8b` model locally.
- Python 3.12+ and [Node.js](https://nodejs.org/) (for the React frontend).
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) with English language data — required for scanned PDFs. On macOS, install with `brew install tesseract`.

## Quick start (dev)

```bash
# 1. Pull the LLM model
ollama pull llama3.1:8b

# 2. Start Ollama in one terminal
ollama serve

# 3. Install and start the backend in another
pip install -e ".[dev]"
# Install Tesseract separately for OCR of scanned PDFs (macOS: brew install tesseract)
CAMPUSGPT_ADMIN_USER=admin CAMPUSGPT_ADMIN_PASS=changeme uvicorn app.main:app --reload

# 4. Start the React frontend
cd frontend && npm install && npm run dev
```

Open the app at `http://localhost:5173`. The API is at `http://localhost:8000`.

## Quick start (Docker)

```bash
docker compose up --build
```

Seed an admin on first run via env vars:

```bash
CAMPUSGPT_ADMIN_USER=admin CAMPUSGPT_ADMIN_PASS=changeme docker compose up --build
```

## Configuration

All settings are read from environment variables with the `CAMPUSGPT_` prefix. The following are mandatory for production:

- `CAMPUSGPT_SESSION_SECRET`: Secret key for session management. **Do not derive this from other variables; use a dedicated secret management tool.**

Optional variables include:

| Variable | Default | Description |
|---|---|---|
| `CAMPUSGPT_DATA_DIR` | `./data` | Root data directory |
| `CAMPUSGPT_OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `CAMPUSGPT_OLLAMA_MODEL` | `llama3.1:8b` | Ollama model name |
| `CAMPUSGPT_EMBEDDING_MODEL_NAME` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model |
| `CAMPUSGPT_TOP_K` | `6` | Retrieval result count |
| `CAMPUSGPT_CONFIDENCE_THRESHOLD` | `0.35` | Refusal threshold |
| `CAMPUSGPT_ADMIN_USER` | *(required)* | First-run admin username |
| `CAMPUSGPT_ADMIN_PASS` | *(required)* | First-run admin password |

## Architecture

![Architecture](architecture overview)

The backend is a FastAPI app serving both the React SPA at `/` and JSON APIs at `/api/*`. ChromaDB stores document embeddings, SQLite stores users/conversations/messages/documents, and Ollama generates answers with inline citations.

For the full design spec, see [docs/superpowers/specs/2026-08-19-campusgpt-design.md](docs/superpowers/specs/2026-08-19-campusgpt-design.md).

## API

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Basic health check |
| `/api/health/deep` | GET | Deep health (Ollama version + Chroma count) |
| `/api/auth/login` | POST | Login |
| `/api/auth/logout` | POST | Logout |
| `/api/auth/me` | GET | Current user |
| `/api/chat` | POST | Send a question |
| `/api/conversations` | GET/POST | List/create conversations |
| `/api/conversations/:id/messages` | GET | Get messages |
| `/api/documents` | GET/POST | List/upload documents |
| `/api/documents/:id` | DELETE | Delete a document |
| `/api/admin/users` | GET/POST | List/create users |
| `/api/admin/users/:id` | DELETE | Delete a user |

See [docs/superpowers/specs/2026-08-19-campusgpt-design.md](docs/superpowers/specs/2026-08-19-campusgpt-design.md) for the full API reference.
