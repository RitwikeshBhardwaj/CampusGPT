"""Message persistence."""

from pathlib import Path

from app.db.connection import connect


def add_message(
    db_path: Path,
    conv_id: int,
    role: str,
    content: str,
    citations_json: str | None = None,
    refused: bool = False,
) -> int:
    with connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO messages (conversation_id, role, content, citations_json, refused) "
            "VALUES (?, ?, ?, ?, ?)",
            (conv_id, role, content, citations_json, int(bool(refused))),
        )
        return cur.lastrowid


def get_messages(db_path: Path, conv_id: int, user_id: int) -> list[dict]:
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT m.* FROM messages m "
            "JOIN conversations c ON c.id = m.conversation_id "
            "WHERE m.conversation_id = ? AND c.user_id = ? "
            "ORDER BY m.created_at ASC, m.id ASC",
            (conv_id, user_id),
        ).fetchall()
        return [dict(r) for r in rows]
