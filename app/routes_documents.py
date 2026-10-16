"""Document routes: upload (admin), list (auth), delete (admin)."""

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.auth import require_role, require_user
from app.config import settings
from app.db import delete_document as db_delete_document
from app.db import get_document, init_db, list_documents
from app.ingest_pipeline import ingest_pdf
from app.pdf_utils import PDFExtractionError
from app.retrieve import get_collection

router = APIRouter(prefix="/api/documents", tags=["documents"])


class DocumentResponse(BaseModel):
    id: int
    filename: str
    pages: int
    chunks: int
    uploaded_at: str


class UploadResponse(BaseModel):
    doc_id: int
    filename: str
    pages: int
    chunks: int


def _to_doc_response(doc: dict) -> DocumentResponse:
    return DocumentResponse(
        id=doc["id"],
        filename=doc["filename"],
        pages=doc["pages"],
        chunks=doc["chunks"],
        uploaded_at=doc["uploaded_at"],
    )


@router.get("", response_model=list[DocumentResponse])
def list_documents_route(user: dict = Depends(require_user)):
    """List all documents. Any authenticated user."""
    init_db(settings.db_path)
    return [_to_doc_response(d) for d in list_documents(settings.db_path)]


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    admin: dict = Depends(require_role("admin")),
):
    """Upload a PDF document. Admin only."""
    settings.ensure_dirs()
    init_db(settings.db_path)

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted",
        )

    safe_name = Path(file.filename).name
    if not safe_name or safe_name in (".", ".."):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename",
        )

    # Stage the uploaded file in a temp file; ingest_pdf will copy it into pdf_dir.
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = Path(tmp.name)
    except Exception:
        tmp_path = None
        raise

    try:
        result = ingest_pdf(tmp_path, safe_name)
    except PDFExtractionError as e:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to ingest PDF",
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    return UploadResponse(
        doc_id=result["doc_id"],
        filename=result["filename"],
        pages=result["pages"],
        chunks=result["chunks"],
    )


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document_route(doc_id: int, admin: dict = Depends(require_role("admin"))):
    """Delete a document: removes PDF, ChromaDB chunks, and SQLite row. Admin only."""
    init_db(settings.db_path)
    doc = get_document(settings.db_path, doc_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    try:
        coll = get_collection(settings.chroma_dir)
        res = coll.get(where={"doc_id": doc_id})
        ids = res.get("ids", [])
        if ids:
            coll.delete(ids=ids)
    except Exception:
        pass

    pdf_path = settings.pdf_dir / doc["filename"]
    pdf_path.unlink(missing_ok=True)

    db_delete_document(settings.db_path, doc_id)
    return None