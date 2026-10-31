from pathlib import Path

import pypdf


class PDFExtractionError(Exception):
    """Raised when a PDF cannot be read (encrypted, scanned, malformed)."""


def extract_pages(path: Path) -> list[tuple[int, str]]:
    """Return [(page_number, text)] with 1-indexed page numbers.

    Pages without a text layer are OCRed locally with Tesseract.
    Raises PDFExtractionError on encrypted, unreadable, or unprocessable PDFs.
    """
    try:
        reader = pypdf.PdfReader(str(path))
    except Exception as exc:
        raise PDFExtractionError(f"Could not open PDF: {exc}") from exc

    if reader.is_encrypted:
        raise PDFExtractionError("PDF is encrypted; password-protected files are not supported.")

    extracted: list[str] = []
    for idx, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            raise PDFExtractionError(f"Could not extract page {idx}: {exc}") from exc
        extracted.append(text.strip())

    pages = [(idx, text) for idx, text in enumerate(extracted, start=1) if text]
    pages_to_ocr = [idx for idx, text in enumerate(extracted) if not text]
    if pages_to_ocr:
        try:
            import pymupdf
        except ImportError as exc:
            raise PDFExtractionError(
                "This PDF needs OCR, but PyMuPDF is not installed. Install the project dependencies."
            ) from exc

        try:
            document = pymupdf.open(str(path))
        except Exception as exc:
            raise PDFExtractionError(
                f"Could not open PDF for OCR: {exc}. "
                "Ensure Tesseract OCR and the English language data are installed."
            ) from exc

        try:
            for page_index in pages_to_ocr:
                page_number = page_index + 1
                try:
                    page = document[page_index]
                    ocr_text_page = page.get_textpage_ocr(
                        language="eng",
                        dpi=300,
                        full=True,
                    )
                    text = page.get_text(textpage=ocr_text_page).strip()
                except Exception as exc:
                    raise PDFExtractionError(
                        f"OCR failed on page {page_number}: {exc}. "
                        "Ensure Tesseract OCR and the English language data are installed."
                    ) from exc
                if text:
                    pages.append((page_number, text))
        finally:
            document.close()

    pages.sort(key=lambda item: item[0])
    if not pages:
        raise PDFExtractionError(
            "No text could be extracted, including OCR. Check the scan quality and that "
            "Tesseract OCR with English language data is installed."
        )
    return pages
