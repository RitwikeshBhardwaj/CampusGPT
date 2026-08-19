from app.db import init_db, add_document, set_chunk_count, list_documents, delete_document


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