"""Simple per-user rate limiter using Redis sliding window."""

from __future__ import annotations

import time
from functools import lru_cache

import redis.asyncio as redis
from fastapi import Depends, HTTPException, status

from app.core.config import settings
from app.core.deps import get_current_user, get_current_user_sse
from app.models.user import User


@lru_cache(maxsize=1)
def _pool() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


async def _check_rate(user_id: int, action: str, max_requests: int, window_seconds: int) -> None:
    r = _pool()
    key = f"rl:{action}:{user_id}"
    now = time.time()
    pipe = r.pipeline()
    pipe.zremrangebyscore(key, 0, now - window_seconds)
    pipe.zadd(key, {str(now): now})
    pipe.zcard(key)
    pipe.expire(key, window_seconds + 10)
    results = await pipe.execute()
    count = results[2]
    if count > max_requests:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Rate limit exceeded: max {max_requests} requests per {window_seconds}s",
        )


async def rate_limit_llm(user: User = Depends(get_current_user)) -> User:
    await _check_rate(user.id, "llm", max_requests=10, window_seconds=60)
    return user


async def rate_limit_llm_sse(user: User = Depends(get_current_user_sse)) -> User:
    """Same rate limit as rate_limit_llm but auth via SSE-compatible token source."""
    await _check_rate(user.id, "llm", max_requests=10, window_seconds=60)
    return user
