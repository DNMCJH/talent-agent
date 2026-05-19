"""Qdrant client wrapper enforcing per-user payload filter.

All upserts and searches REQUIRE a user_id. There is one Qdrant collection
for projects; tenants are isolated via payload.user_id filter on every query.

Vector dim defaults to 1024 (BGE-m3). For BGE-small the caller passes 512.
"""

from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qm

from app.core.config import settings


@lru_cache(maxsize=1)
def _client() -> AsyncQdrantClient:
    kwargs: dict[str, Any] = {"url": settings.qdrant_url}
    if settings.qdrant_api_key:
        kwargs["api_key"] = settings.qdrant_api_key
    return AsyncQdrantClient(**kwargs)


async def ensure_projects_collection(vector_size: int = 1024) -> None:
    """Idempotently create the projects collection with a payload index on user_id."""
    client = _client()
    name = settings.qdrant_collection_projects
    existing = await client.get_collections()
    if not any(c.name == name for c in existing.collections):
        await client.create_collection(
            collection_name=name,
            vectors_config=qm.VectorParams(size=vector_size, distance=qm.Distance.COSINE),
        )
    # Payload index on user_id is critical for efficient multi-tenant filtering.
    try:
        await client.create_payload_index(
            collection_name=name,
            field_name="user_id",
            field_schema=qm.PayloadSchemaType.INTEGER,
        )
    except Exception:
        # Already exists — fine
        pass


def _user_filter(user_id: int, extra: list[qm.FieldCondition] | None = None) -> qm.Filter:
    must: list[qm.FieldCondition] = [
        qm.FieldCondition(key="user_id", match=qm.MatchValue(value=user_id)),
    ]
    if extra:
        must.extend(extra)
    return qm.Filter(must=must)


async def upsert_project(
    user_id: int,
    project_id: int,
    vector: list[float],
    payload: dict[str, Any],
) -> str:
    """Upsert a project vector. Returns the Qdrant point id (UUID string).

    payload is augmented with user_id and project_id; caller's payload wins for other keys.
    """
    client = _client()
    name = settings.qdrant_collection_projects
    point_id = str(uuid.uuid4())
    merged = {**payload, "user_id": user_id, "project_id": project_id}
    await client.upsert(
        collection_name=name,
        points=[qm.PointStruct(id=point_id, vector=vector, payload=merged)],
    )
    return point_id


async def search_projects(
    user_id: int,
    query_vector: list[float],
    limit: int = 10,
    score_threshold: float | None = None,
) -> list[qm.ScoredPoint]:
    """Search projects belonging to this user only. Cross-tenant leakage is impossible
    because the user_id filter is applied server-side by Qdrant."""
    client = _client()
    name = settings.qdrant_collection_projects
    res = await client.query_points(
        collection_name=name,
        query=query_vector,
        query_filter=_user_filter(user_id),
        limit=limit,
        score_threshold=score_threshold,
    )
    return res.points


async def delete_project(user_id: int, project_id: int) -> None:
    """Delete all points for a (user_id, project_id) pair. The user_id check guards
    against deleting another tenant's data even if project_id is guessed."""
    client = _client()
    name = settings.qdrant_collection_projects
    await client.delete(
        collection_name=name,
        points_selector=qm.FilterSelector(
            filter=_user_filter(
                user_id,
                extra=[qm.FieldCondition(key="project_id", match=qm.MatchValue(value=project_id))],
            )
        ),
    )


async def count_user_projects(user_id: int) -> int:
    client = _client()
    name = settings.qdrant_collection_projects
    res = await client.count(collection_name=name, count_filter=_user_filter(user_id))
    return res.count
