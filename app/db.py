import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    pages INTEGER NOT NULL,
    chunks INTEGER NOT NULL DEFAULT 0,
    uploaded_at TEXT DEFAULT (datetime('now'))
);
"""


def _conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path) -> None:
    with _conn(db_path) as conn:
        conn.executescript(SCHEMA)


def add_document(db_path: Path, filename: str, pages: int) -> int:
    with _conn(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO documents (filename, pages) VALUES (?, ?)",
            (filename, pages),
        )
        return cur.lastrowid


def set_chunk_count(db_path: Path, doc_id: int, count: int) -> None:
    with _conn(db_path) as conn:
        conn.execute("UPDATE documents SET chunks = ? WHERE id = ?", (count, doc_id))


def list_documents(db_path: Path) -> list[dict]:
    with _conn(db_path) as conn:
        rows = conn.execute("SELECT * FROM documents ORDER BY uploaded_at DESC").fetchall()
        return [dict(r) for r in rows]


def delete_document(db_path: Path, doc_id: int) -> str | None:
    with _conn(db_path) as conn:
        cur = conn.execute("SELECT filename FROM documents WHERE id = ?", (doc_id,))
        row = cur.fetchone()
        if not row:
            return None
        filename = row["filename"]
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        return filename


def get_document(db_path: Path, doc_id: int) -> dict | None:
    with _conn(db_path) as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return dict(row) if row else None