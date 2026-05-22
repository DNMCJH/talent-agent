"""Lazy singleton embedder. sentence-transformers loads BGE on first use."""

from __future__ import annotations

import asyncio
import threading
from functools import lru_cache

from app.core.config import settings

# Serializes the one-time model load: warmup (background, see app.main) and a
# real request can race during a deploy — without this both would load BGE.
_load_lock = threading.Lock()


@lru_cache(maxsize=1)
def _build_embedder():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embed_model, device=settings.embed_device)


def get_embedder():
    with _load_lock:
        return _build_embedder()


def embed_text(text: str) -> list[float]:
    return get_embedder().encode(text, normalize_embeddings=True).tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch encode — much faster than calling embed_text in a loop."""
    if not texts:
        return []
    arr = get_embedder().encode(texts, normalize_embeddings=True, batch_size=32)
    return [v.tolist() for v in arr]


async def embed_text_async(text: str) -> list[float]:
    return await asyncio.to_thread(embed_text, text)


async def embed_texts_async(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return await asyncio.to_thread(embed_texts, texts)


def project_doc_to_text(name: str, readme: str, stack: list[str], topics: list[str]) -> str:
    """Stable text representation for embedding a ProjectDoc."""
    parts = [
        f"Project: {name}",
        f"Stack: {', '.join(stack)}" if stack else "",
        f"Topics: {', '.join(topics)}" if topics else "",
        readme[:4000],
    ]
    return "\n".join(p for p in parts if p)
