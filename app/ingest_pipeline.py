import shutil
from pathlib import Path

from app.config import settings
from app.db import add_document, init_db, set_chunk_count, delete_document
from app.document_utils import DocumentExtractionError, extract_text_from_docx, extract_text_from_txt
from app.ingest import chunk_pages
from app.pdf_utils import PDFExtractionError, extract_pages
from app.retrieve import add_chunks, get_collection, get_model


def ingest_document(doc_path: Path, filename: str) -> dict:
    """Extract pages/text, chunk, embed, and store any supported document format.

    Supports: .pdf, .docx, .txt
    On any failure after the file copy, the file is removed to keep state clean.
    """
    settings.ensure_dirs()
    init_db(settings.db_path)

    ext = filename.lower().split('.')[-1]
    dest = settings.pdf_dir / filename  # Still using pdf_dir for all documents
    shutil.copy(doc_path, dest)

    try:
        if ext == 'pdf':
            pages = extract_pages(dest)
        elif ext == 'txt':
            text = extract_text_from_txt(dest)
            # Treat as single page
            pages = [(1, text)]
        elif ext in ('docx', 'doc'):
            paragraphs = extract_text_from_docx(dest)
            # Treat as single page with all paragraphs joined
            pages = [(1, "\n\n".join(paragraphs))]
        else:
            dest.unlink(missing_ok=True)
            raise DocumentExtractionError(f"Unsupported file type: {ext}")
    except (PDFExtractionError, DocumentExtractionError):
        dest.unlink(missing_ok=True)
        raise

    chunks = chunk_pages(pages)
    if not chunks:
        dest.unlink(missing_ok=True)
        raise DocumentExtractionError("No chunks could be produced from this document.")

    doc_id = add_document(settings.db_path, filename=filename, pages=len(pages))

    try:
        model = get_model()
        add_chunks(doc_id=doc_id, doc_name=filename, chunks=chunks, model=model)
    except Exception:
        # Rollback: remove the chunks we may have written, the DB row, and the file.
        coll = get_collection(settings.chroma_dir)
        ids = [f"doc{doc_id}-p{c.page}-c{c.chunk_index}" for c in chunks]
        try:
            coll.delete(ids=ids)
        except Exception:
            pass
        delete_document(settings.db_path, doc_id)
        dest.unlink(missing_ok=True)
        raise

    set_chunk_count(settings.db_path, doc_id, count=len(chunks))
    return {
        "doc_id": doc_id,
        "filename": filename,
        "pages": len(pages),
        "chunks": len(chunks),
    }


def ingest_pdf(pdf_path: Path, filename: str) -> dict:
    """Legacy wrapper for PDF ingestion. Prefer ingest_document."""
    return ingest_document(pdf_path, filename)