"""SSE response helpers shared across API routers."""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

import redis.asyncio as redis
from fastapi import HTTPException, status

from app.core.config import settings

_logger = logging.getLogger(__name__)


def sse_format(event: dict[str, Any]) -> str:
    """Serialize a dict as a single SSE `data:` line.

    ensure_ascii=False so Chinese characters travel literally — browsers handle
    UTF-8, and it's significantly smaller than escaped \\uXXXX sequences.
    """
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


async def wrap_sse(gen: AsyncIterator[dict[str, Any]]) -> AsyncIterator[str]:
    """Convert a service-layer event stream into SSE-formatted strings.

    Appends a terminal `[DONE]` sentinel; emits an error event on exception so
    the client always sees a terminal signal even when something fails.
    """
    try:
        async for event in gen:
            yield sse_format(event)
    except HTTPException as e:
        # HTTPException.detail is intentional client-facing copy; safe to forward.
        yield sse_format({"type": "error", "status": e.status_code, "message": e.detail})
    except Exception:  # noqa: BLE001 — last-ditch catch so client sees something
        # Do not echo raw exception text to the client: it may leak provider
        # error bodies, internal paths, or stack-adjacent context. Log server-
        # side with a request id and return a generic message keyed on that id.
        request_id = uuid.uuid4().hex[:12]
        _logger.exception("SSE stream failed (request_id=%s)", request_id)
        yield sse_format({
            "type": "error",
            "status": 500,
            "message": f"internal stream error (request_id={request_id})",
            "request_id": request_id,
        })
    yield "data: [DONE]\n\n"


SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    # Disable nginx response buffering so chunks flush to the client immediately.
    "X-Accel-Buffering": "no",
}


# ---------------------------------------------------------------------------
# Staged stream payloads
#
# EventSource can only issue GET requests, so naively a stream's input (JD text,
# interview answers) would travel in the URL query string and leak into access
# logs / browser history. Instead the client POSTs the payload to a `prepare`
# endpoint, which stages it in Redis under an opaque id; the SSE GET then carries
# only that id. Payloads are one-time use and short-lived.
# ---------------------------------------------------------------------------

_STREAM_TTL = 300  # seconds — long enough to open the EventSource, short enough to expire fast


@lru_cache(maxsize=1)
def _stream_redis() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


async def stage_stream_payload(user_id: int, payload: dict[str, Any]) -> str:
    """Store a stream request payload server-side and return an opaque id."""
    stream_id = uuid.uuid4().hex
    blob = json.dumps({"user_id": user_id, "payload": payload})
    await _stream_redis().set(f"sse:pending:{stream_id}", blob, ex=_STREAM_TTL)
    return stream_id


async def pop_stream_payload(stream_id: str, user_id: int) -> dict[str, Any]:
    """Fetch and atomically delete a staged payload (one-time use).

    Raises 404 if missing/expired, 403 if it belongs to a different user.
    """
    blob = await _stream_redis().getdel(f"sse:pending:{stream_id}")
    if blob is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "stream request expired or already consumed"
        )
    data = json.loads(blob)
    if data.get("user_id") != user_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "stream request does not belong to this user"
        )
    return data["payload"]
