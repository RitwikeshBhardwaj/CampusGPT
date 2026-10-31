"""Data access layer, split by entity.

Re-exports every accessor so existing `from app.db import ...` call sites
keep working unchanged.
"""

from app.db.connection import SCHEMA, init_db
from app.db.conversations import (
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversations,
    rename_conversation,
)
from app.db.documents import (
    add_document,
    delete_document,
    get_document,
    list_documents,
    set_chunk_count,
)
from app.db.messages import add_message, get_messages
from app.db.users import (
    create_user,
    delete_user,
    get_user_by_id,
    get_user_by_username,
    list_users,
    update_user_password,
)

__all__ = [
    "SCHEMA",
    "init_db",
    "add_document",
    "set_chunk_count",
    "list_documents",
    "delete_document",
    "get_document",
    "create_user",
    "get_user_by_username",
    "get_user_by_id",
    "list_users",
    "delete_user",
    "update_user_password",
    "create_conversation",
    "list_conversations",
    "get_conversation",
    "rename_conversation",
    "delete_conversation",
    "add_message",
    "get_messages",
]
