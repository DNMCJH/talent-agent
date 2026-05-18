"""Indexer CLI: scan projects and upsert to Qdrant."""

from __future__ import annotations

import asyncio

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from talent_agent.config import settings
from talent_agent.indexer.scanner import scan_all_projects


def _build_embed_text(doc) -> str:
    return f"{doc.name} {' '.join(doc.topics)} {' '.join(doc.stack)} {doc.readme[:2000]}"


async def run_index():
    print(f"Scanning projects in {settings.projects_root}...")
    projects = await scan_all_projects()
    print(f"Found {len(projects)} projects to index.")

    if not projects:
        print("No projects found. Check PROJECTS_ROOT and INDEX_EXCLUDE in .env")
        return

    print(f"Loading embedding model {settings.embed_model}...")
    embedder = SentenceTransformer(settings.embed_model, device=settings.embed_device)

    texts = [_build_embed_text(p) for p in projects]
    print("Generating embeddings...")
    vectors = embedder.encode(texts, show_progress_bar=True, normalize_embeddings=True)

    print(f"Connecting to Qdrant...")
    if settings.qdrant_url:
        qdrant = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
    else:
        from pathlib import Path
        Path(settings.qdrant_local_path).mkdir(parents=True, exist_ok=True)
        qdrant = QdrantClient(path=settings.qdrant_local_path)

    collection = settings.qdrant_collection_projects
    dim = vectors.shape[1]

    collections = [c.name for c in qdrant.get_collections().collections]
    if collection not in collections:
        qdrant.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        print(f"Created collection '{collection}' (dim={dim})")

    points = [
        PointStruct(
            id=i,
            vector=vectors[i].tolist(),
            payload=projects[i].model_dump(),
        )
        for i in range(len(projects))
    ]

    qdrant.upsert(collection_name=collection, points=points)
    print(f"Indexed {len(points)} projects into '{collection}'.")


def main():
    asyncio.run(run_index())


if __name__ == "__main__":
    main()
