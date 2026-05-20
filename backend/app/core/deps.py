"""FastAPI dependencies: current user resolution from Bearer JWT."""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import decode_jwt, decode_stream_token
from app.core.db import get_session
from app.models.user import User


async def get_current_user(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_jwt(token)
    except Exception as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid token: {exc}") from exc

    user_id = int(payload["sub"])
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")
    return user


async def get_optional_user(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> User | None:
    """For demo-mode endpoints that work both anonymously and authenticated."""
    if not authorization:
        return None
    try:
        return await get_current_user(authorization, session)
    except HTTPException:
        return None


async def get_current_user_sse(
    authorization: str | None = Header(default=None),
    token: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Auth for SSE endpoints: EventSource cannot set custom headers, so accept a
    `?token=...` query param with a short-lived stream token.

    Header (Bearer) takes precedence when both are present.
    """
    user_id: int | None = None

    if authorization and authorization.lower().startswith("bearer "):
        raw_token = authorization.split(" ", 1)[1]
        try:
            payload = decode_jwt(raw_token)
            user_id = int(payload["sub"])
        except Exception as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid token: {exc}") from exc
    elif token:
        try:
            user_id = decode_stream_token(token)
        except Exception as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid stream token: {exc}") from exc
    else:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing token")

    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")
    return user


# Silence unused import warning — kept for explicit re-export
__all__ = [
    "get_current_user",
    "get_current_user_sse",
    "get_optional_user",
    "select",
]
