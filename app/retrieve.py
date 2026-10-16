from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

from app.ingest import Chunk
from app.log_config import log_retrieval


COLLECTION_NAME = "campusgpt_chunks"


@dataclass
class Source:
    doc_id: int
    doc_name: str
    page: int
    chunk_index: int
    text: str
    score: float


@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    from app.config import settings
    return SentenceTransformer(settings.embedding_model_name)


def get_collection(persist_dir: Path):
    client = chromadb.PersistentClient(path=str(persist_dir))
    return client.get_or_create_collection(
        name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )


def _chunk_id(doc_id: int, page: int, chunk_index: int) -> str:
    return f"doc{doc_id}-p{page}-c{chunk_index}"


def add_chunks(
    doc_id: int,
    doc_name: str,
    chunks: list[Chunk],
    model: SentenceTransformer | None = None,
    persist_dir: Path | None = None,
) -> None:
    from app.config import settings
    model = model or get_model()
    persist_dir = persist_dir or settings.chroma_dir
    if not chunks:
        return
    texts = [c.text for c in chunks]
    embeddings = model.encode(texts, convert_to_numpy=True).tolist()
    ids = [_chunk_id(doc_id, c.page, c.chunk_index) for c in chunks]
    metadatas = [
        {"doc_id": doc_id, "doc_name": doc_name, "page": c.page, "chunk_index": c.chunk_index}
        for c in chunks
    ]
    coll = get_collection(persist_dir)
    coll.upsert(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)


def retrieve(
    query: str,
    top_k: int = 6,
    model: SentenceTransformer | None = None,
    persist_dir: Path | None = None,
) -> list[Source]:
    from app.config import settings
    model = model or get_model()
    persist_dir = persist_dir or settings.chroma_dir
    coll = get_collection(persist_dir)
    q_emb = model.encode([query], convert_to_numpy=True).tolist()
    res = coll.query(query_embeddings=q_emb, n_results=top_k)
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]
    sources: list[Source] = []
    for text, meta, dist in zip(docs, metas, dists):
        # cosine distance → similarity in [0,1]; higher score = more relevant
        score = max(0.0, 1.0 - float(dist))
        sources.append(
            Source(
                doc_id=int(meta["doc_id"]),
                doc_name=str(meta["doc_name"]),
                page=int(meta["page"]),
                chunk_index=int(meta["chunk_index"]),
                text=text,
                score=score,
            )
        )
    log_retrieval(
        query=query,
        top_k=top_k,
        num_results=len(sources),
        persist_dir=str(persist_dir),
    )
    return sources