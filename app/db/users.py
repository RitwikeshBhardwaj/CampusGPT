"""User persistence."""

from pathlib import Path

from app.db.connection import connect


def create_user(db_path: Path, username: str, password_hash: str, role: str) -> int:
    with connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (username, password_hash, role),
        )
        return cur.lastrowid


def get_user_by_username(db_path: Path, username: str) -> dict | None:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None


def get_user_by_id(db_path: Path, user_id: int) -> dict | None:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def list_users(db_path: Path) -> list[dict]:
    with connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at ASC").fetchall()
        return [dict(r) for r in rows]


def delete_user(db_path: Path, user_id: int) -> None:
    with connect(db_path) as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def update_user_password(db_path: Path, user_id: int, password_hash: str) -> None:
    with connect(db_path) as conn:
        conn.execute("UPDATE users SET password = ? WHERE id = ?", (password_hash, user_id))
