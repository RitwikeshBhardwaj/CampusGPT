from dataclasses import dataclass
import re


@dataclass
class Chunk:
    text: str
    page: int
    chunk_index: int


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_TABLE_CELL_SPLIT = re.compile(r"[ \t]{2,}|\t|\|")


def _is_table_line(line: str) -> bool:
    """A line is table-like if it has at least 2 cells separated by 2+ spaces or a tab."""
    cells = [c for c in _TABLE_CELL_SPLIT.split(line) if c.strip()]
    return len(cells) >= 2


def is_table_page(text: str) -> bool:
    """True when at least 3 consecutive non-empty lines are table-like."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    consecutive = 0
    for ln in lines:
        if _is_table_line(ln):
            consecutive += 1
            if consecutive >= 3:
                return True
        else:
            consecutive = 0
    return False


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_SPLIT.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def chunk_pages(pages: list[tuple[int, str]], target_chars: int = 2000) -> list[Chunk]:
    """Split each page's text on sentence boundaries into ~target_chars chunks.

    Table-like pages (>= 3 consecutive lines with 2+ spaced cells) are split
    into one chunk per row, with the header row prepended to each row chunk.
    Chunks never cross page boundaries. chunk_index resets per page.
    """
    chunks: list[Chunk] = []
    for page_num, text in pages:
        lines = text.split("\n")
        if is_table_page(text):
            header = lines[0].strip()
            idx = 0
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue
                chunks.append(Chunk(text=f"{header} | {line}", page=page_num, chunk_index=idx))
                idx += 1
            continue
        sentences = _split_sentences(text)
        buffer = ""
        idx = 0
        for sent in sentences:
            # If adding this sentence would overflow and buffer is non-empty, flush.
            if buffer and len(buffer) + 1 + len(sent) > target_chars:
                chunks.append(Chunk(text=buffer, page=page_num, chunk_index=idx))
                idx += 1
                buffer = sent
            else:
                buffer = (buffer + " " + sent).strip() if buffer else sent
        if buffer:
            chunks.append(Chunk(text=buffer, page=page_num, chunk_index=idx))
    return chunks
