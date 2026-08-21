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

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('student', 'admin')),
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
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    citations_json TEXT,
    refused INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


def _conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
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


# --- Users ---------------------------------------------------------------

def create_user(db_path: Path, username: str, password_hash: str, role: str) -> int:
    with _conn(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (username, password_hash, role),
        )
        return cur.lastrowid


def get_user_by_username(db_path: Path, username: str) -> dict | None:
    with _conn(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None


def get_user_by_id(db_path: Path, user_id: int) -> dict | None:
    with _conn(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def list_users(db_path: Path) -> list[dict]:
    with _conn(db_path) as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at ASC").fetchall()
        return [dict(r) for r in rows]


def delete_user(db_path: Path, user_id: int) -> None:
    with _conn(db_path) as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def update_user_password(db_path: Path, user_id: int, password_hash: str) -> None:
    with _conn(db_path) as conn:
        conn.execute("UPDATE users SET password = ? WHERE id = ?", (password_hash, user_id))


# --- Conversations --------------------------------------------------------

def create_conversation(db_path: Path, user_id: int, title: str | None = None) -> int:
    with _conn(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO conversations (user_id, title) VALUES (?, ?)",
            (user_id, title),
        )
        return cur.lastrowid


def list_conversations(db_path: Path, user_id: int) -> list[dict]:
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM conversations WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_conversation(db_path: Path, conv_id: int, user_id: int) -> dict | None:
    with _conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ? AND user_id = ?",
            (conv_id, user_id),
        ).fetchone()
        return dict(row) if row else None


def delete_conversation(db_path: Path, conv_id: int, user_id: int) -> bool:
    with _conn(db_path) as conn:
        row = conn.execute(
            "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
            (conv_id, user_id),
        ).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        return True


# --- Messages -------------------------------------------------------------

def add_message(
    db_path: Path,
    conv_id: int,
    role: str,
    content: str,
    citations_json: str | None = None,
    refused: bool = False,
) -> int:
    with _conn(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO messages (conversation_id, role, content, citations_json, refused) "
            "VALUES (?, ?, ?, ?, ?)",
            (conv_id, role, content, citations_json, int(bool(refused))),
        )
        return cur.lastrowid


def get_messages(db_path: Path, conv_id: int, user_id: int) -> list[dict]:
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT m.* FROM messages m "
            "JOIN conversations c ON c.id = m.conversation_id "
            "WHERE m.conversation_id = ? AND c.user_id = ? "
            "ORDER BY m.created_at ASC, m.id ASC",
            (conv_id, user_id),
        ).fetchall()
        return [dict(r) for r in rows]