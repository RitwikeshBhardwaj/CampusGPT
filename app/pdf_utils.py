from pathlib import Path

import pypdf


class PDFExtractionError(Exception):
    """Raised when a PDF cannot be read (encrypted, scanned, malformed)."""


def extract_pages(path: Path) -> list[tuple[int, str]]:
    """Return [(page_number, text)] with 1-indexed page numbers.

    Raises PDFExtractionError on encrypted or unreadable PDFs.
    Pages with no extractable text are skipped.
    """
    try:
        reader = pypdf.PdfReader(str(path))
    except Exception as exc:
        raise PDFExtractionError(f"Could not open PDF: {exc}") from exc

    if reader.is_encrypted:
        raise PDFExtractionError("PDF is encrypted; password-protected files are not supported.")

    pages: list[tuple[int, str]] = []
    for idx, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            raise PDFExtractionError(f"Could not extract page {idx}: {exc}") from exc
        text = text.strip()
        if text:
            pages.append((idx, text))
    if not pages:
        raise PDFExtractionError("No extractable text found. Scanned PDFs require OCR, which is not yet supported.")
    return pages
