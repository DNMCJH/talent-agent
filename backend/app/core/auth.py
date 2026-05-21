"""GitHub OAuth code exchange + JWT issuing for session tokens.

Flow: frontend (NextAuth.js) sends GitHub OAuth `code` to /auth/github.
Backend exchanges code for access_token, fetches user profile, upserts a
User row, and returns a backend-signed JWT used as the Bearer token for
all subsequent API calls.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import jwt

from app.core.config import settings

JWT_ALG = "HS256"
JWT_TTL_DAYS = 30


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return salt.hex() + ":" + dk.hex()


def verify_password(password: str, stored: str) -> bool:
    salt_hex, dk_hex = stored.split(":", 1)
    salt = bytes.fromhex(salt_hex)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return hmac.compare_digest(dk.hex(), dk_hex)


class OAuthError(Exception):
    pass


async def exchange_github_code(code: str) -> str:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
    if resp.status_code != 200:
        raise OAuthError(f"github token endpoint {resp.status_code}")
    body = resp.json()
    token = body.get("access_token")
    if not token:
        raise OAuthError(f"no access_token in response: {body}")
    return token


async def fetch_github_user(access_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"},
        )
    if resp.status_code != 200:
        raise OAuthError(f"github user endpoint {resp.status_code}")
    return resp.json()


async def verify_github_token(access_token: str) -> dict[str, Any]:
    """Validate that `access_token` was issued for THIS OAuth app and return the
    associated GitHub user profile.

    Uses GitHub's `POST /applications/{client_id}/token` check endpoint, which is
    authenticated with client_id:client_secret. A token minted for a different
    OAuth app — or a forged one — cannot pass this check, so the returned profile
    can be trusted as the caller's real identity.
    """
    if not settings.github_client_id or not settings.github_client_secret:
        raise OAuthError("github oauth not configured")
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"https://api.github.com/applications/{settings.github_client_id}/token",
            auth=(settings.github_client_id, settings.github_client_secret),
            json={"access_token": access_token},
            headers={"Accept": "application/vnd.github+json"},
        )
    if resp.status_code != 200:
        raise OAuthError(f"github token check failed ({resp.status_code})")
    user = resp.json().get("user")
    if not user:
        raise OAuthError("github token check returned no user")
    return user


def issue_jwt(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(UTC) + timedelta(days=JWT_TTL_DAYS),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.api_secret, algorithm=JWT_ALG)


def decode_jwt(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.api_secret, algorithms=[JWT_ALG])


# Email verification tokens — short-lived JWTs with a distinct `purpose` claim
# so a stolen verification link cannot be used as a session token.
EMAIL_VERIFY_TTL_HOURS = 24


def issue_email_verify_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "purpose": "email_verify",
        "exp": datetime.now(UTC) + timedelta(hours=EMAIL_VERIFY_TTL_HOURS),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.api_secret, algorithm=JWT_ALG)


def decode_email_verify_token(token: str) -> int:
    """Returns user_id if token is valid and has the right purpose; raises otherwise."""
    payload = jwt.decode(token, settings.api_secret, algorithms=[JWT_ALG])
    if payload.get("purpose") != "email_verify":
        raise jwt.InvalidTokenError("wrong token purpose")
    return int(payload["sub"])


# Password reset tokens — short TTL so a leaked reset link expires quickly.
PASSWORD_RESET_TTL_HOURS = 1


def issue_password_reset_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "purpose": "password_reset",
        "exp": datetime.now(UTC) + timedelta(hours=PASSWORD_RESET_TTL_HOURS),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.api_secret, algorithm=JWT_ALG)


def decode_password_reset_token(token: str) -> int:
    payload = jwt.decode(token, settings.api_secret, algorithms=[JWT_ALG])
    if payload.get("purpose") != "password_reset":
        raise jwt.InvalidTokenError("wrong token purpose")
    return int(payload["sub"])


# SSE stream tokens — short-lived so they can safely appear in query params / logs.
SSE_TOKEN_TTL_MINUTES = 5


def issue_stream_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "purpose": "stream",
        "exp": datetime.now(UTC) + timedelta(minutes=SSE_TOKEN_TTL_MINUTES),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.api_secret, algorithm=JWT_ALG)


def decode_stream_token(token: str) -> int:
    payload = jwt.decode(token, settings.api_secret, algorithms=[JWT_ALG])
    if payload.get("purpose") != "stream":
        raise jwt.InvalidTokenError("wrong token purpose — expected stream token")
    return int(payload["sub"])
