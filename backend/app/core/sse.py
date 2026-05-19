"""SSE response helpers shared across API routers."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import HTTPException


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
        yield sse_format({"type": "error", "status": e.status_code, "message": e.detail})
    except Exception as e:  # noqa: BLE001 — last-ditch catch so client sees something
        yield sse_format({"type": "error", "status": 500, "message": str(e)})
    yield "data: [DONE]\n\n"


SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    # Disable nginx response buffering so chunks flush to the client immediately.
    "X-Accel-Buffering": "no",
}
