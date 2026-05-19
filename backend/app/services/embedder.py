"""Lazy singleton embedder. sentence-transformers loads BGE on first use."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings


@lru_cache(maxsize=1)
def get_embedder():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embed_model, device=settings.embed_device)


def embed_text(text: str) -> list[float]:
    return get_embedder().encode(text, normalize_embeddings=True).tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch encode — much faster than calling embed_text in a loop."""
    if not texts:
        return []
    arr = get_embedder().encode(texts, normalize_embeddings=True, batch_size=32)
    return [v.tolist() for v in arr]


def project_doc_to_text(name: str, readme: str, stack: list[str], topics: list[str]) -> str:
    """Stable text representation for embedding a ProjectDoc."""
    parts = [
        f"Project: {name}",
        f"Stack: {', '.join(stack)}" if stack else "",
        f"Topics: {', '.join(topics)}" if topics else "",
        readme[:4000],
    ]
    return "\n".join(p for p in parts if p)
