# RAG Evaluation Categories Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the running CampusGPT app behave correctly against five RAG evaluation categories — direct fact retrieval precision, multi-document synthesis, tabular data extraction, out-of-scope refusal, and conflicting-data conflict surfacing — each backed by a test that fails before the change and passes after.

**Architecture:** Minimal product changes to `app/ingest.py` (row-chunk table detection) and `app/answer.py` (one conflict-instruction line in `build_prompt`). New test file `tests/test_eval_categories.py` plus a strengthened assertion in `tests/test_eval.py`. No live Ollama required; retrieval tests use the real embedder (skipped offline), answer tests feed fake Ollama responses or assert the model is never called (refusal path).

**Tech Stack:** Python 3.11+, FastAPI, pypdf, sentence-transformers, chromadb, sqlite3, pytest, httpx.

**Spec:** `docs/superpowers/specs/2026-10-16-rag-eval-categories-design.md`

---

## Global Constraints

- Python 3.11+ is required (uses `tomllib`, modern type hints).
- All Python source lives under `app/` and `tests/`.
- Confidence threshold for refusal: `0.35` (similarity score normalized to 0–1; higher = more relevant).
- Retrieval `top_k = 6`.
- Chunk target size: ~2000 characters, sentence-aware, never cross page boundaries.
- Embedding model: `sentence-transformers/all-MiniLM-L6-v2` (loaded once via `@lru_cache`, cached).
- LLM: `llama3.1:8b` via Ollama at `http://localhost:11434/api/generate`.
- Hallucinated citation numbers (`[N]` where `N > len(sources)`) MUST be silently dropped before the response is returned.
- All persistence lives under `./data/` (created on first run): `./data/pdfs/`, `./data/chroma/`, `./data/campusgpt.db`.
- All commits end with `Co-Authored-By: Claude <noreply@anthropic.com>`.
- Commit messages use Conventional Commits (`feat:`, `test:`, `chore:`, `docs:`, `fix:`).

---

## Review Focus

1. **Prose table on one line** — a real PDF table flattened into a single wrapped line by pypdf will not be detected; it falls back to sentence chunking (acceptable until pointed at an actual handbook). Owned by Task 2.
2. **Single document crowds out the other** in a multi-document query — top-6 may return chunks from only one document; a second-query merge is added only if Task 4's test shows crowd-out.
3. **Model ignores the conflict instruction** — the test asserts the instruction is in the prompt and that an answer citing both sources parses; it cannot assert a real model follows it without Ollama. Verified live after you connect Ollama. Owned by Task 3.
4. **Out-of-scope question scores just above 0.35** — the refusal threshold is fixed at 0.35; a borderline unrelated chunk won't refuse. Owned by Task 5.
5. **Chunk IDs collide** — table row chunks use `doc{doc_id}-p{page}-c{chunk_index}` like all chunks; multiple table rows on one page get distinct chunk_index. Owned by Task 2.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `app/ingest.py` | `chunk_pages` plus new `is_table_page` detection and row-chunk splitting |
| `app/answer.py` | `build_prompt` — add one conflict-instruction line |
| `tests/test_eval_categories.py` | New: five category tests + conflict-prompt test |
| `tests/test_eval.py` | Strengthen existing keyword test to direct fact precision (top hit contains fact) |

---

## Tasks

### Task 1: Direct Fact Retrieval precision test

**Files:**
- Modify: `tests/test_eval.py`

**Interfaces:**
- Consumes: `retrieve(query, top_k, model, persist_dir) -> list[Source]` (existing signature).
- Produces: none (test only; locks in existing retrieval behavior).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_eval.py` a new test `test_eval_retrieval_top_hit_precision` that seeds the corpus from `eval_questions.json`-style chunks, queries each question, and asserts the **top result's text** contains the expected fact string (not merely a keyword somewhere in top 3). It reuses the `seeded_corpus` fixture pattern and skips offline like `test_eval_retrieval_matches_keywords`.

```python
def test_eval_retrieval_top_hit_precision(chroma_dir, seeded_corpus):
    cases = [
        ("What is the minimum graduation credit requirement?", "120 credits"),
        ("What is the scholarship eligibility?", "CGPA 8.5"),
        ("What is the attendance policy?", "75 percent"),
    ]
    for question, expected_fact in cases:
        results = retrieve(question, top_k=3, model=seeded_corpus, persist_dir=chroma_dir)
        assert results, f"No results for '{question}'"
        assert expected_fact.lower() in results[0].text.lower(), (
            f"Top hit for '{question}' does not contain '{expected_fact}'. Got: {results[0].text!r}"
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_eval.py::test_eval_retrieval_top_hit_precision -v`
Expected: FAIL (test does not exist yet → collection error) or assertion FAIL if retrieval ranks a different chunk first.

- [ ] **Step 3: Write minimal implementation**

No product change — retrieval already exists. If the test passes, skip to Step 4. If it fails because a wrong chunk ranks first, add a tiny boost in `app/retrieve.py` only then (not anticipated).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_eval.py::test_eval_retrieval_top_hit_precision -v`
Expected: PASS (or skipped if embedding model unavailable offline).

- [ ] **Step 5: Commit**

```bash
git add tests/test_eval.py
git commit -m "test: direct fact retrieval precision assertion"
```

---

### Task 2: Tabular data extraction — row-chunk table detection

**Files:**
- Create: `tests/test_ingest_table.py` (or add to `tests/test_ingest.py`)
- Modify: `app/ingest.py`

**Interfaces:**
- Consumes: `chunk_pages(pages: list[tuple[int, str]], target_chars: int = 2000) -> list[Chunk]` (existing signature).
- Produces: `is_table_page(text: str) -> bool` (new helper in `app/ingest.py`) and row chunks from `chunk_pages` for table pages.

- [ ] **Step 1: Write the failing test**

```python
from app.ingest import Chunk, chunk_pages


def test_table_page_splits_into_row_chunks_with_header():
    page_text = (
        "Fee | Amount | Frequency\n"
        "Tuition | 45000 | per semester\n"
        "Hostel | 12000 | per semester\n"
        "Library | 2000 | per year\n"
    )
    chunks = chunk_pages([(1, page_text)], target_chars=2000)
    assert len(chunks) == 3, f"expected 3 row chunks, got {len(chunks)}"
    assert all(c.page == 1 for c in chunks)
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1
    assert chunks[2].chunk_index == 2
    assert "Tuition" in chunks[0].text and "45000" in chunks[0].text
    assert "Hostel" in chunks[1].text and "12000" in chunks[1].text
    assert "Library" in chunks[2].text and "2000" in chunks[2].text
    # Header repeated on every row
    assert all("Fee" in c.text and "Amount" in c.text for c in chunks)


def test_prose_page_unchanged_by_table_detection():
    page_text = "Graduation requires 120 credits minimum. Attendance is 75 percent."
    chunks = chunk_pages([(1, page_text)], target_chars=2000)
    assert len(chunks) == 1
    assert chunks[0].text == page_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ingest_table.py -v`
Expected: FAIL — `is_table_page` does not exist; `chunk_pages` does not split tables into rows.

- [ ] **Step 3: Write minimal implementation**

In `app/ingest.py`, add:

```python
_TABLE_CELL_SPLIT = re.compile(r"[ \t]{2,}|\t")


def _is_table_line(line: str) -> bool:
    """A line is table-like if it has at least 2 cells separated by 2+ spaces or a tab."""
    cells = [c for c in _TABLE_CELL_SPLIT.split(line) if c.strip()]
    return len(cells) >= 2


def is_table_page(text: str) -> bool:
    """True when at least 3 consecutive non-empty lines are table-like."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    consecutive = 0
    for ln in lines:
        if _is_table_line(ln):
            consecutive += 1
            if consecutive >= 3:
                return True
        else:
            consecutive = 0
    return False
```

Then modify `chunk_pages` to route table pages through row chunking:

```python
def chunk_pages(pages: list[tuple[int, str]], target_chars: int = 2000) -> list[Chunk]:
    """Split each page's text on sentence boundaries into ~target_chars chunks.

    Table-like pages (>= 3 consecutive lines with 2+ spaced cells) are split
    into one chunk per row, with the header row prepended to each row chunk.
    Chunks never cross page boundaries. chunk_index resets per page.
    """
    chunks: list[Chunk] = []
    for page_num, text in pages:
        lines = text.split("\n")
        if is_table_page(text):
            header = lines[0].strip()
            idx = 0
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue
                chunks.append(Chunk(text=f"{header} | {line}", page=page_num, chunk_index=idx))
                idx += 1
            continue
        sentences = _split_sentences(text)
        buffer = ""
        idx = 0
        for sent in sentences:
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

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ingest_table.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/ingest.py tests/test_ingest_table.py
git commit -m "feat: table page detection splits into row chunks with header"
```

---

### Task 3: Conflicting data — conflict instruction in answer prompt

**Files:**
- Create: `tests/test_answer_conflict.py`
- Modify: `app/answer.py`

**Interfaces:**
- Consumes: `build_prompt(sources: list[Source], question: str) -> str` (existing), `parse_citations(answer_text, sources) -> tuple[str, list[Citation]]` (existing).
- Produces: `build_prompt` output now includes a conflict-instruction line.

- [ ] **Step 1: Write the failing test**

```python
from app.answer import build_prompt, parse_citations
from app.retrieve import Source


def test_build_prompt_contains_conflict_instruction():
    sources = [
        Source(1, "regulations.pdf", 4, 0, "Graduation requires 120 credits minimum.", 0.9),
        Source(2, "catalog.pdf", 2, 0, "Graduation requires 130 credits minimum.", 0.85),
    ]
    prompt = build_prompt(sources, "How many credits to graduate?")
    assert "disagree" in prompt.lower() or "conflict" in prompt.lower()
    assert "Do not pick one" in prompt or "do not pick one" in prompt.lower()


def test_parse_citations_keeps_both_conflicting_sources():
    sources = [
        Source(1, "regulations.pdf", 4, 0, "120 credits minimum.", 0.9),
        Source(2, "catalog.pdf", 2, 0, "130 credits minimum.", 0.85),
    ]
    answer = "Handbook says 120 credits [1]. Catalog says 130 credits [2]. These conflict."
    cleaned, citations = parse_citations(answer, sources)
    assert len(citations) == 2
    numbers = {c.number for c in citations}
    assert numbers == {1, 2}
    assert citations[0].doc_name == "regulations.pdf"
    assert citations[1].doc_name == "catalog.pdf"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_answer_conflict.py -v`
Expected: FAIL — `build_prompt` has no conflict instruction; prompt assertion fails.

- [ ] **Step 3: Write minimal implementation**

Add one line to `build_prompt` in `app/answer.py`, after the "Never make up information." line:

```
If the sources disagree on the same fact, quote both versions and state that they conflict. Do not pick one.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_answer_conflict.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/answer.py tests/test_answer_conflict.py
git commit -m "feat: conflict instruction in answer prompt (surface both versions)"
```

---

### Task 4: Multi-document synthesis test

**Files:**
- Create: `tests/test_eval_categories.py`

**Interfaces:**
- Consumes: `retrieve(query, top_k, model, persist_dir) -> list[Source]` (existing).
- Produces: none (test only; verification of existing top-6 behavior).

- [ ] **Step 1: Write the failing test**

```python
import json
from pathlib import Path

import pytest

from app.retrieve import retrieve, add_chunks, get_collection
from app.ingest import Chunk


@pytest.fixture
def chroma_dir(tmp_path):
    d = tmp_path / "chroma"
    d.mkdir()
    return d


def _model():
    pytest.importorskip("sentence_transformers")
    from sentence_transformers import SentenceTransformer
    try:
        return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    except Exception:
        pytest.skip("Embedding model not available offline")


def test_multi_document_synthesis_retrieves_both_files(chroma_dir):
    model = _model()
    handbook = [
        Chunk("Tuition is 45000 per semester.", 1, 0),
        Chunk("Hostel fee is 12000 per semester.", 2, 0),
    ]
    fees = [
        Chunk("Library deposit is 2000 refundable.", 1, 0),
        Chunk("Exam fee is 1500 per year.", 2, 0),
    ]
    add_chunks(doc_id=1, doc_name="handbook.pdf", chunks=handbook, model=model, persist_dir=chroma_dir)
    add_chunks(doc_id=2, doc_name="fees.pdf", chunks=fees, model=model, persist_dir=chroma_dir)

    results = retrieve("total semester cost including hostel and library", top_k=6, model=model, persist_dir=chroma_dir)
    doc_names = {r.doc_name for r in results}
    assert "handbook.pdf" in doc_names, f"handbook missing; got {doc_names}"
    assert "fees.pdf" in doc_names, f"fees missing; got {doc_names}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_eval_categories.py::test_multi_document_synthesis_retrieves_both_files -v`
Expected: FAIL — test file does not exist, or if top-6 crowds out one document, the assertion fails.

- [ ] **Step 3: Write minimal implementation**

No product change yet — run first. If `fees.pdf` is crowded out of top-6, add a second retrieval query against the missing document and merge results in `app/retrieve.py` (or a new helper). Anticipated: top-6 over 6 chunks returns all, so this passes with no product change.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_eval_categories.py::test_multi_document_synthesis_retrieves_both_files -v`
Expected: PASS (or skipped offline).

- [ ] **Step 5: Commit**

```bash
git add tests/test_eval_categories.py
git commit -m "test: multi-document synthesis retrieves both files"
```

---

### Task 5: Out-of-scope refusal test

**Files:**
- Modify: `tests/test_eval_categories.py`

**Interfaces:**
- Consumes: `retrieve(...) -> list[Source]`, `generate_answer(question, sources) -> AnswerResult`, `should_refuse(sources) -> bool` (all existing).
- Produces: none (test only; locks in existing refusal behavior).

- [ ] **Step 1: Write the failing test**

```python
from app.answer import generate_answer, should_refuse
from app.retrieve import Source


def test_out_of_scope_refuses_without_calling_llm(monkeypatch):
    sources = [
        Source(1, "handbook.pdf", 1, 0, "Tuition is 45000 per semester.", 0.20),
        Source(2, "handbook.pdf", 2, 0, "Hostel fee is 12000 per semester.", 0.15),
    ]
    assert should_refuse(sources) is True

    called = {"llm": False}

    async def fake_post(*args, **kwargs):
        called["llm"] = True
        raise AssertionError("LLM should not be called for out-of-scope question")

    import app.answer as answer_mod
    monkeypatch.setattr(answer_mod.httpx.AsyncClient, "post", fake_post)

    result = generate_answer("What is the capital of France?", sources)
    assert result.refused is True
    assert result.answer == "I don't have enough information in the provided documents to answer this question."
    assert result.citations == []
    assert called["llm"] is False
    assert result.closest_source is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_eval_categories.py::test_out_of_scope_refuses_without_calling_llm -v`
Expected: FAIL — test does not exist yet.

- [ ] **Step 3: Write minimal implementation**

No product change — `should_refuse` and `generate_answer` already implement refusal without calling the LLM. If the test passes, proceed to Step 4.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_eval_categories.py::test_out_of_scope_refuses_without_calling_llm -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_eval_categories.py
git commit -m "test: out-of-scope question refuses without calling LLM"
```

---

## Self-Review Notes

**Spec coverage:**

| Spec section | Task |
|---|---|
| §1 Direct Fact Retrieval precision | Task 1 |
| §2 Multi-document synthesis | Task 4 |
| §3 Tabular data extraction | Task 2 |
| §4 Out-of-scope refusal | Task 5 |
| §5 Conflicting data conflict prompt | Task 3 |
| No live Ollama in tests | All tasks |
| Option B (surface both, no ranking) | Task 3 |

**Placeholder scan:** No TBDs, no "implement later", no "add appropriate error handling" without code. Every step has code blocks.

**Type consistency:**
- `Source` (dataclass, `app.retrieve`) used consistently in Tasks 1, 4, 5.
- `Chunk` (dataclass, `app.ingest`) used in Task 2.
- `Citation` (Pydantic, `app.models`) used in Task 3 via `parse_citations`.
- `is_table_page(text: str) -> bool` new helper in `app/ingest.py`, consumed only by `chunk_pages`.
- `build_prompt(sources, question) -> str` signature unchanged; only body gains a line.

**Review Focus coverage:**
1. Prose table on one line → Task 2 (falls back to sentence chunking; documented limitation).
2. Single document crowds out other → Task 4 (second-query merge only if test shows crowd-out).
3. Model ignores conflict instruction → Task 3 (prompt instruction + parse test; live verification deferred).
4. Borderline score just above 0.35 → Task 5 (fixed threshold; documented).
5. Chunk ID collisions → Task 2 (distinct chunk_index per row on a page).

**Gaps:** None found. All five spec sections map to a task; each task has write-failing-test → run → implement → run-pass → commit steps.

---

**Plan complete and saved to `docs/superpowers/plans/2026-10-16-rag-eval-categories.md`.** The user already said "do this as of now," so I'll proceed with native execution via `superpowers:executing-plans` unless you'd prefer subagent-driven review per task.
