"""Conversation persistence."""

from pathlib import Path

from app.db.connection import connect


def create_conversation(db_path: Path, user_id: int, title: str | None = None) -> int:
    with connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO conversations (user_id, title) VALUES (?, ?)",
            (user_id, title),
        )
        return cur.lastrowid


def list_conversations(db_path: Path, user_id: int) -> list[dict]:
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM conversations WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_conversation(db_path: Path, conv_id: int, user_id: int) -> dict | None:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ? AND user_id = ?",
            (conv_id, user_id),
        ).fetchone()
        return dict(row) if row else None


def rename_conversation(db_path: Path, conv_id: int, user_id: int, title: str) -> bool:
    """Set a conversation's title. Returns False when it isn't owned by the user."""
    with connect(db_path) as conn:
        cur = conn.execute(
            "UPDATE conversations SET title = ? WHERE id = ? AND user_id = ?",
            (title, conv_id, user_id),
        )
        return cur.rowcount > 0


def delete_conversation(db_path: Path, conv_id: int, user_id: int) -> bool:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
            (conv_id, user_id),
        ).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        return True
