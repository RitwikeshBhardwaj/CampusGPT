from app.db import (
    init_db,
    add_document, set_chunk_count, list_documents, delete_document,
    create_user, get_user_by_username, get_user_by_id, list_users, delete_user,
    create_conversation, list_conversations, get_conversation, delete_conversation,
    add_message, get_messages,
)


def test_document_lifecycle(tmp_path):
    db = tmp_path / "c.db"
    init_db(db)
    assert list_documents(db) == []
    doc_id = add_document(db, "regulations.pdf", pages=42)
    set_chunk_count(db, doc_id, 100)
    docs = list_documents(db)
    assert len(docs) == 1
    assert docs[0]["filename"] == "regulations.pdf"
    assert docs[0]["pages"] == 42
    assert docs[0]["chunks"] == 100
    fname = delete_document(db, doc_id)
    assert fname == "regulations.pdf"


def test_init_db_is_idempotent(tmp_path):
    db = tmp_path / "c.db"
    init_db(db)
    init_db(db)  # no error
    add_document(db, "x.pdf", pages=1)


# --- Users -----------------------------------------------------------------

def test_user_create_and_lookup(tmp_path):
    db = tmp_path / "c.db"
    init_db(db)
    uid = create_user(db, "alice", "hashed_pw", "admin")
    assert uid > 0
    by_name = get_user_by_username(db, "alice")
    assert by_name is not None
    assert by_name["id"] == uid
    assert by_name["role"] == "admin"
    by_id = get_user_by_id(db, uid)
    assert by_id["username"] == "alice"
    assert get_user_by_username(db, "nobody") is None


def test_list_and_delete_users(tmp_path):
    db = tmp_path / "c.db"
    init_db(db)
    create_user(db, "a", "h", "student")
    create_user(db, "b", "h", "admin")
    assert len(list_users(db)) == 2
    users = list_users(db)
    ids = [u["id"] for u in users]
    delete_user(db, ids[0])
    assert len(list_users(db)) == 1


def test_duplicate_username_raises(tmp_path):
    import sqlite3
    db = tmp_path / "c.db"
    init_db(db)
    create_user(db, "dupe", "h", "student")
    import pytest
    with pytest.raises(sqlite3.IntegrityError):
        create_user(db, "dupe", "h", "admin")


# --- Conversations ---------------------------------------------------------

def test_conversation_lifecycle_and_ownership(tmp_path):
    db = tmp_path / "c.db"
    init_db(db)
    u1 = create_user(db, "owner", "h", "student")
    u2 = create_user(db, "other", "h", "student")

    cid = create_conversation(db, u1, title="first chat")
    assert cid > 0
    assert len(list_conversations(db, u1)) == 1
    assert list_conversations(db, u2) == []

    # Only the owner can fetch the conversation
    assert get_conversation(db, cid, u1) is not None
    assert get_conversation(db, cid, u2) is None

    # Delete by non-owner is a no-op
    assert delete_conversation(db, cid, u2) is False
    assert get_conversation(db, cid, u1) is not None
    # Delete by owner succeeds
    assert delete_conversation(db, cid, u1) is True
    assert get_conversation(db, cid, u1) is None


# --- Messages --------------------------------------------------------------

def test_messages_ordered_and_owned(tmp_path):
    import json
    db = tmp_path / "c.db"
    init_db(db)
    uid = create_user(db, "owner", "h", "student")
    cid = create_conversation(db, uid, title="chat")

    m1 = add_message(db, cid, "user", "What credits to graduate?")
    m2 = add_message(db, cid, "assistant", "120 credits [1].",
                    citations_json=json.dumps([{"number": 1, "doc_name": "reg.pdf", "page": 4, "passage": "120 credits."}]))
    assert m1 > 0 and m2 > 0

    msgs = get_messages(db, cid, uid)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"
    assert msgs[0]["id"] < msgs[1]["id"]
    assert json.loads(msgs[1]["citations_json"])[0]["number"] == 1
    assert msgs[0]["citations_json"] is None
    assert msgs[1]["refused"] == 0


def test_messages_not_visible_to_other_user(tmp_path):
    db = tmp_path / "c.db"
    init_db(db)
    u1 = create_user(db, "owner", "h", "student")
    u2 = create_user(db, "other", "h", "student")
    cid = create_conversation(db, u1, title="secret")
    add_message(db, cid, "user", "private")
    # get_messages enforces ownership via the conversation join
    assert get_messages(db, cid, u2) == []
    assert len(get_messages(db, cid, u1)) == 1


def test_delete_cascade_removes_messages(tmp_path):
    db = tmp_path / "c.db"
    init_db(db)
    uid = create_user(db, "owner", "h", "student")
    cid = create_conversation(db, uid, title="chat")
    add_message(db, cid, "user", "hi")
    delete_conversation(db, cid, uid)
    # Messages are gone with the conversation
    assert get_messages(db, cid, uid) == []