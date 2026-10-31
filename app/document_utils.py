"""Text extraction for DOCX and TXT files."""

from pathlib import Path


class DocumentExtractionError(Exception):
    """Raised when document extraction fails."""
    pass


def extract_text_from_txt(path: Path) -> str:
    """Extract plain text from a .txt file."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Try latin-1 as fallback
        try:
            return path.read_text(encoding="latin-1")
        except Exception as e:
            raise DocumentExtractionError(f"Failed to decode text file: {e}")
    except Exception as e:
        raise DocumentExtractionError(f"Failed to read text file: {e}")


def extract_text_from_docx(path: Path) -> list[str]:
    """Extract paragraphs from a .docx file.

    Returns a list of paragraph texts (one per paragraph in the document).
    """
    try:
        from docx import Document
    except ImportError:
        raise DocumentExtractionError(
            "python-docx is required for DOCX support. Install it with: pip install python-docx"
        )

    try:
        doc = Document(str(path))
        paragraphs = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                paragraphs.append(text)
        if not paragraphs:
            raise DocumentExtractionError("No text content found in DOCX")
        return paragraphs
    except Exception as e:
        if isinstance(e, DocumentExtractionError):
            raise
        raise DocumentExtractionError(f"Failed to extract DOCX: {e}")
