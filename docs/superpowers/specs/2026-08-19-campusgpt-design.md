# CampusGPT — Design Spec

CampusGPT is a fully local Retrieval-Augmented Generation (RAG) system that lets university students and admins ask natural-language questions against a shared library of PDF documents (academic regulations, exam notices, scholarship guidelines, course syllabi, hostel rules, placement documents, department notices) and receive grounded answers with inline citations.

---

## 1. Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI |
| Frontend | React (Vite) |
| Vector store | ChromaDB (persistent, `./chroma/`) |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` (runs in-process) |
| LLM | Ollama running `llama3.1:8b` locally |
| PDF extraction | pypdf |
| Relational store | SQLite (`./campusgpt.db`) |
| Password hashing | bcrypt via passlib |
| Session management | Signed session token in `httpOnly` cookie |

---

## 2. Architecture

```
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  React Web UI    │───▶│  FastAPI backend │───▶│  Ollama (LLM)    │
│  (chat + admin)  │    │  (Python)        │    │  Llama 3.1 8B    │
└──────────────────┘    └────────┬─────────┘    └──────────────────┘
                                 │
                  ┌──────────────┼──────────────┐
                  ▼              ▼              ▼
            ┌──────────┐  ┌──────────┐  ┌──────────────┐
            │ ChromaDB │  │ SQLite   │  │ ./pdfs/      │
            │ vectors  │  │ metadata │  │ raw PDFs     │
            └──────────┘  └──────────┘  └──────────────┘
```

Three separate processes:

1. **Ollama** — started once via `ollama serve`, listens on `localhost:11434`.
2. **FastAPI backend** — exposes API endpoints; also serves the React static build at `/`.
3. **React frontend** — single-page app with routing for `/`, `/login`, `/admin`.

---

## 3. Backend modules

| File | Responsibility |
|---|---|
| `app/main.py` | FastAPI app, route registration, static-file mount, session/auth middleware |
| `app/auth.py` | Login, logout, signup (admin-only), session cookie management, `get_current_user` dependency |
| `app/ingest.py` | PDF upload → page-aware chunking → embedding → upsert to ChromaDB |
| `app/retrieve.py` | Embed question, ChromaDB top_k search, return chunks with metadata |
| `app/answer.py` | Build grounded prompt, call Ollama, parse citations, enforce refusal threshold |
| `app/models.py` | Pydantic schemas: `QuestionRequest`, `AnswerResponse`, `Citation`, `UploadResponse`, `UserCreate` |
| `app/db.py` | SQLite access: users table, conversations/messages tables, document metadata |
| `app/pdf_utils.py` | Extract text page-by-page with pypdf, return list of `(page_num, text)` tuples |

---

## 4. Data model (SQLite)

```sql
-- Users
CREATE TABLE users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT UNIQUE NOT NULL,
    password    TEXT NOT NULL,        -- bcrypt hash
    role        TEXT NOT NULL CHECK (role IN ('student', 'admin')),
    created_at  TEXT DEFAULT (datetime('now'))
);

-- Conversations
CREATE TABLE conversations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

-- Messages
CREATE TABLE messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    citations_json  TEXT,             -- JSON array of Citation objects, NULL for user messages
    refused         INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- Documents (admin-managed)
CREATE TABLE documents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT NOT NULL,
    pages       INTEGER NOT NULL,
    chunks      INTEGER NOT NULL DEFAULT 0,
    uploaded_at TEXT DEFAULT (datetime('now'))
);
```

---

## 5. Authorization rules

| Role | Can do |
|---|---|
| `student` | Ask questions (`/api/chat`), view own conversation history |
| `admin` | Everything students can do + upload/delete documents (`/api/documents`), create/delete users (`/api/admin/users`) |

Enforcement:

- **Frontend:** hides UI elements the user can't access (upload button, user list).
- **Server:** every route is decorated with `require_role` (or `get_current_user` where no role is needed). This is the source of truth.

First-run admin account is seeded from environment variables:

```bash
CAMPUSGPT_ADMIN_USER=admin CAMPUSGPT_ADMIN_PASS=<password> python -m app.main
```

Signup endpoint exists but only accepts requests when the caller is already an admin.

---

## 6. PDF ingestion

1. Admin drops a PDF via `/admin` (or calls `POST /api/documents` directly).
2. File is saved to `./pdfs/<uuid>.pdf`.
3. Row inserted into `documents` (filename, page_count).
4. `pdf_utils.extract_pages` iterates pages via pypdf:
   - Returns `(page_number, text)` per page; page numbers are 1-indexed.
   - If a page yields no text (encrypted or scanned), ingestion is aborted with a 400 and the file is cleaned up.
5. `ingest.chunk_pages` splits each page's text into chunks:
   - Target: ~500 tokens (~2000 characters).
   - Split on sentence boundaries; never split mid-sentence.
   - Chunks never cross page boundaries — page number is attached as metadata to every chunk.
6. `sentence-transformers/all-MiniLM-L6-v2` embeds all chunks in batch.
7. Chunks are upserted to ChromaDB with metadata:
   ```json
   {
     "doc_id": 3,
     "doc_name": "academic_regulations_2026.pdf",
     "page": 12,
     "chunk_index": 0,
     "text": "The minimum credit requirement for graduation is 120..."
   }
   ```
8. SQLite `documents.chunks` is updated to reflect the final count.

---

## 7. Retrieval and answering

### Retrieval

1. Embed the user's question with `all-MiniLM-L6-v2`.
2. ChromaDB similarity search: `top_k=6`.
3. Return each hit: `{doc_name, page, chunk_index, text, score}`.

### Confidence gate

- Best score `< 0.35`: **refuse to answer.**
  - Return refusal message plus the nearest source so the user can check it.
- Best score `>= 0.35`: proceed to answer generation.

### Prompt

```
System:
You are CampusGPT, a university document assistant.
Answer the user's question using ONLY the numbered sources provided below.
Cite sources in your answer as [1], [2], etc.
If the answer is not fully contained in the sources, say "I don't have
enough information in the provided documents to answer this question."
Never make up information.

Sources:
[1] academic_regulations_2026.pdf, p.12 — "The minimum credit requirement for graduation is 120..."
[2] scholarship_guidelines.pdf, p.3 — "Eligibility requires a CGPA of 8.5 or higher..."

User: <question>
```

### Response parsing

- Regex `\[([1-9][0-9]*)\]` extracts cited numbers.
- Any citation `[N]` where `N > len(sources)` is silently dropped (guards against hallucinated citation numbers).
- If the generated text contains no citations and no refusal string, a weak-warning flag is set:
  `warning: "This answer may not be fully grounded in the source documents."`

---

## 8. API endpoints

| Method | Path | Auth | Role | Description |
|---|---|---|---|---|
| `POST` | `/api/auth/login` | no | — | Body: `{username, password}`. Sets session cookie. Returns `{user, role}`. |
| `POST` | `/api/auth/logout` | yes | any | Clears session cookie. |
| `GET`  | `/api/auth/me` | yes | any | Returns current user info. |
| `POST` | `/api/admin/users` | yes | admin | Create a user: `{username, password, role}`. |
| `DELETE` | `/api/admin/users/:id` | yes | admin | Delete a user. |
| `GET` | `/api/admin/users` | yes | admin | List all users. |
| `GET` | `/api/conversations` | yes | any | List current user's conversations. |
| `POST` | `/api/conversations` | yes | any | Create new conversation. Returns `{id}`. |
| `DELETE` | `/api/conversations/:id` | yes | owner | Delete a conversation (and its messages). |
| `GET` | `/api/conversations/:id/messages` | yes | owner | Get messages for a conversation. |
| `POST` | `/api/chat` | yes | any | Body: `{question, conversation_id}`. Returns `AnswerResponse`. |
| `POST` | `/api/documents` | yes | admin | Upload a PDF (`multipart/form-data`). |
| `GET` | `/api/documents` | yes | any | List all documents with metadata. |
| `DELETE` | `/api/documents/:id` | yes | admin | Delete a document and all its chunks. |
| `GET` | `/api/health` | no | — | Returns LLM + ChromaDB status. |

---

## 9. Frontend pages

| Path | Description |
|---|---|
| `/login` | Username + password form. No public signup. |
| `/` | Chat view. Sidebar shows conversation list + "New Chat" button. Main area: message thread. Inline `[N]` citations render as clickable chips; clicking opens a panel showing `doc_name`, `page`, and the highlighted passage. |
| `/admin` | Two tabs: **Documents** (upload drag-and-drop, list with delete) and **Users** (create/delete). |

UI notes:

- Refusal messages render in a distinct style (yellow/orange, with the suggested source shown below).
- Warning messages render with a subtle flag icon.
- Responsive, but not mobile-first — this is primarily a desktop campus tool.

---

## 10. Error handling

| Failure | Behavior |
|---|---|
| Non-PDF upload | 400: "Only PDF files are supported." File discarded. |
| Scanned / encrypted PDF | 400: "Could not extract text. OCR is not yet supported." File cleaned up. |
| Ollama unreachable | 503: "LLM server (Ollama) is not running. Start it with `ollama serve`." |
| ChromaDB write failure mid-ingest | Rollback: remove partially-ingested chunks, delete PDF file, 500 with message. |
| Hallucinated `[N]` citation (`N > len(sources)`) | Silently dropped before response is returned. |
| No citations in response + no refusal | Warning flag added to response; UI displays it. |
| Frontend can't reach backend | Banner: "Cannot reach server" with retry button. |
| Refusal triggered | UI renders refusal in distinct style with the closest matching source. |

---

## 11. Logging

- Python `logging` to stdout, structured JSON.
- One log line per request: `{timestamp, path, user_id, latency_ms, top_scores[], refused, citations_count}`.
- Ingestion events: `{timestamp, doc_id, pages, chunks, latency_ms}`.

---

## 12. Testing strategy

### Unit tests (`tests/`)

| Module | Coverage |
|---|---|
| `pdf_utils.py` | Multi-page extraction, encrypted PDF rejection, empty-page handling |
| `retrieve.py` | Mock embedding, assert top_k shape and metadata |
| `answer.py` | Citation parsing, hallucinated citation drop, refusal trigger, warning flag |
| `auth.py` | Password hashing, session cookie creation, role enforcement |

Framework: `pytest` + `pytest-asyncio`.

### Integration tests

- Ingest a real 5-page PDF → verify chunk count, SQLite row, ChromaDB entry.
- Seed 3 PDFs → ask a known question → verify answer contains correct citation and passage.
- Ask an out-of-scope question → verify refusal path.
- Full auth flow: create user, login, verify protected endpoints, verify role restriction.

### Eval set

`tests/eval_questions.json` — ~10 question/keyword pairs. Run after every prompt or chunking change.

### Manual smoke

- Upload a real campus PDF, ask the 5 example questions from the brief.
- Verify citation chips open the panel with correct source and passage.
- Test refusal with an out-of-scope question.
- Create a student account, verify they can't access `/admin`.
- Delete a document, confirm it no longer appears in answers.

---

## 13. Phased delivery

### Phase 1 — Ingestion + CLI retrieval (no UI)

- Project structure and FastAPI skeleton (`/api/health`).
- `pdf_utils` — page-wise extraction.
- `ingest` — chunking + ChromaDB storage.
- `retrieve` — embedding query + similarity search.
- `answer` — prompt building + Ollama call + citation parsing.
- `db.py` — SQLite schema + document metadata.
- CLI: `python -m campusgpt.ask "question"` prints the answer + citations.

### Phase 2 — Auth + conversation persistence + web UI

- `auth.py` — login, session cookie, `get_current_user`, `require_role`.
- `models.py` — full Pydantic schemas.
- DB migrations for `users`, `conversations`, `messages`.
- `/api/auth/*`, `/api/conversations/*`, `/api/chat` wired up.
- React app: `/login`, `/` (chat + conversation sidebar), `/admin` (document tab).
- FastAPI serves the built React app as static files.

### Phase 3 — Honest-answer controls + admin features

- Refusal path (confidence threshold + "not in docs").
- Citation hallucination guard.
- Eval set + structured request logging.
- `/api/admin/users` (create, list, delete).
- `/admin` — Users tab.
- Document delete endpoint + UI.

### Phase 4 — Polish

- Health endpoint reports LLM + ChromaDB status.
- Dockerfile + `docker-compose.yml` (Ollama + backend in one command).
- README with setup, first-run steps, and example usage.
