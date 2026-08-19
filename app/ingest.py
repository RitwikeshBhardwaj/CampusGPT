from dataclasses import dataclass
import re


@dataclass
class Chunk:
    text: str
    page: int
    chunk_index: int


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_SPLIT.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def chunk_pages(pages: list[tuple[int, str]], target_chars: int = 2000) -> list[Chunk]:
    """Split each page's text on sentence boundaries into ~target_chars chunks.

    Chunks never cross page boundaries. chunk_index resets per page.
    """
    chunks: list[Chunk] = []
    for page_num, text in pages:
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
