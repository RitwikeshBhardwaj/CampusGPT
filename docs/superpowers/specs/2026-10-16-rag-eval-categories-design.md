# CampusGPT — RAG evaluation categories design

**Status:** Approved for implementation  
**Branch:** `feat/campusgpt`  
**Approach:** B — product behavior first, then tests that drive it  
**Conflict policy:** Option B — surface both versions and note the conflict; do not pick one, no recency ranking

## Goal

Implement five evaluation behaviors so the running app (not just a test stub) can be checked against:

1. Direct Fact Retrieval — basic vector similarity & precision
2. Multi-Hop / Multi-Document Synthesis — pull from two separate files
3. Structured / Tabular Data Extraction — PDF/table parsing
4. Out-of-Scope / Unanswerable — admit missing context instead of hallucinating
5. Conflicting Data / Temporal Edge Cases — surface both versions, note conflict

## Scope

Product changes:

- `app/ingest.py` — `chunk_pages` detects table-like page text and emits one chunk per table row (header repeated on each row).
- `app/answer.py` — `build_prompt` gains a conflict instruction; otherwise unchanged.
- No changes to `app/retrieve.py` yet; multi-document synthesis is verified with top-6 retrieval first. A second-query merge is added only if the test shows one document crowds the other out.

Test changes (no live LLM required):

- Extend / add tests under `tests/` covering each category. Retrieval tests use the real embedder (skipped when offline, matching `tests/test_eval.py`). Answer tests feed a fake Ollama response or assert the model is never called (refusal path).

## What each category does after implementation

### 1. Direct Fact Retrieval

**Behavior:** Unchanged retrieval. The correct chunk is the top hit for a fact-specific question.

**Test:** Seeds a small corpus, queries for a specific fact, asserts the top result's text contains that fact (stronger than "at least one keyword appears somewhere in top 3").

**Product change:** None — locks in existing vector search.

### 2. Multi-Hop / Multi-Document Synthesis

**Behavior:** A question whose answer requires two documents retrieves chunks from both documents within top-6.

**Test:** Seeds `handbook.pdf` and `fees.pdf`; asks a question needing both; asserts returned sources include both filenames.

**Product change:** None yet. If top-6 returns only one document, add a second query over the other document and merge results. Added only if the test demonstrates crowd-out.

### 3. Structured / Tabular Data Extraction

**Behavior:** `chunk_pages` detects a page whose lines contain two or more cells separated by two+ spaces or a tab (at least three consecutive such lines). The first line is the header; each following line is its own chunk with the header prepended via ` | `. Non-table pages go through the existing sentence chunker unchanged.

**Test:** Builds table-like lines directly, runs `chunk_pages`, asserts one chunk per row and that each row chunk contains its cell value plus the header context. No PDF, no embedder needed.

**Product change:** `app/ingest.py` — add `is_table_page` and split table pages into row chunks inside `chunk_pages`.

### 4. Out-of-Scope / Unanswerable

**Behavior:** `should_refuse` returns True when the best similarity score is under `confidence_threshold` (0.35). `generate_answer` returns the fixed refusal text without calling `_call_ollama`.

**Test:** Seeds an unrelated corpus, queries something absent, asserts `refused=True`, the fixed refusal answer, no citations, and `_call_ollama` is never invoked.

**Product change:** None — locks in existing refusal behavior.

### 5. Conflicting Data / Temporal Edge Cases

**Behavior (Option B):** `build_prompt` gains:

> If the sources disagree on the same fact, quote both versions and state that they conflict. Do not pick one.

No recency ranking, no "prefer newer document" logic.

**Test:** Builds two disagreeing sources, feeds a model reply that cites both `[1]...[2]`, runs `parse_citations`, asserts both citations survive, and asserts the conflict instruction appears in `build_prompt` output. Does not assert a real model follows the instruction (no live Ollama); that is verified after you connect Ollama.

**Product change:** `app/answer.py` — add one line to `build_prompt`.

## Test file layout

- `tests/test_eval.py` — keep existing keyword-matching test; strengthen or add precision assertions for direct fact retrieval.
- `tests/test_eval_categories.py` — new file with one parametrized test per category plus the conflict-prompt test.
- Fixtures live inline in the tests (small corpora), not as separate PDF files, so tests run without Ollama and without network.

## Success criteria

Each category has a failing test before its product change and a passing test after. Tests do not require Ollama. Direct-fact and refusal tests are deterministic given a seeded corpus. Multi-document test may reveal a need for a second retrieval query; that is a follow-up change, not blocking.

## Out of scope for this implementation

- A full PDF table parser (pdfplumber/camelot). Row-chunk detection on `pypdf`-extracted text is the YAGNI version; upgrade if flattened tables prove unreadable on real handbooks.
- Live Ollama end-to-end tests. You will connect Ollama after this implementation and verify the real model follows the conflict instruction.
- Recency ranking or version-based winner selection for conflicting data (Option B rejected ranking).
