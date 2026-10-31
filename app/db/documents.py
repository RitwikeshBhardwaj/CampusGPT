"""Document persistence."""

from pathlib import Path

from app.db.connection import connect


def add_document(db_path: Path, filename: str, pages: int) -> int:
    with connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO documents (filename, pages) VALUES (?, ?)",
            (filename, pages),
        )
        return cur.lastrowid


def set_chunk_count(db_path: Path, doc_id: int, count: int) -> None:
    with connect(db_path) as conn:
        conn.execute("UPDATE documents SET chunks = ? WHERE id = ?", (count, doc_id))


def list_documents(db_path: Path) -> list[dict]:
    with connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM documents ORDER BY uploaded_at DESC").fetchall()
        return [dict(r) for r in rows]


def delete_document(db_path: Path, doc_id: int) -> str | None:
    with connect(db_path) as conn:
        cur = conn.execute("SELECT filename FROM documents WHERE id = ?", (doc_id,))
        row = cur.fetchone()
        if not row:
            return None
        filename = row["filename"]
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        return filename


def get_document(db_path: Path, doc_id: int) -> dict | None:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return dict(row) if row else None
