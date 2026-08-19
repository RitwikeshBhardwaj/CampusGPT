import os
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_data_dir(monkeypatch):
    d = Path(tempfile.mkdtemp(prefix="campusgpt-test-"))
    monkeypatch.setenv("CAMPUSGPT_DATA_DIR", str(d))
    yield d
    shutil.rmtree(d, ignore_errors=True)


def write_sample_pdf(path, pages_text: list[str]) -> None:
    """Create a real multi-page PDF with extractable text, no extra libraries."""

    def escape(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    n = len(pages_text)
    page_ids = []
    content_ids = []
    next_id = 4
    for _ in pages_text:
        page_ids.append(next_id)
        content_ids.append(next_id + 1)
        next_id += 2

    kids = " ".join(f"{i} 0 R" for i in page_ids)
    objects: list[tuple[int, str]] = [
        (1, "<< /Type /Catalog /Pages 2 0 R >>"),
        (2, f"<< /Type /Pages /Kids [{kids}] /Count {n} >>"),
        (3, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"),
    ]
    for i, text in enumerate(pages_text):
        stream = f"BT /F1 12 Tf 72 720 Td ({escape(text)}) Tj ET"
        objects.append((
            page_ids[i],
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {content_ids[i]} 0 R "
            f"/Resources << /Font << /F1 3 0 R >> >> >>",
        ))
        objects.append((
            content_ids[i],
            f"<< /Length {len(stream.encode('latin-1'))} >>\nstream\n{stream}\nendstream",
        ))

    objects.sort(key=lambda item: item[0])
    out = bytearray(b"%PDF-1.4\n")
    offsets = {0: 0}
    for num, body in objects:
        offsets[num] = len(out)
        out.extend(f"{num} 0 obj\n{body}\nendobj\n".encode("latin-1"))

    xref_pos = len(out)
    size = max(offsets) + 1
    out.extend(f"xref\n0 {size}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for i in range(1, size):
        out.extend(f"{offsets[i]:010d} 00000 n \n".encode())
    out.extend(
        f"trailer\n<< /Root 1 0 R /Size {size} >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    )
    Path(path).write_bytes(bytes(out))

