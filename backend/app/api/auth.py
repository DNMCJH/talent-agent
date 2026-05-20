from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import jwt

from app.core.auth import (
    OAuthError,
    decode_email_verify_token,
    decode_password_reset_token,
    exchange_github_code,
    fetch_github_user,
    hash_password,
    issue_email_verify_token,
    issue_jwt,
    issue_password_reset_token,
    verify_password,
)
from app.core.config import settings
from app.core.db import get_session
from app.core.deps import get_current_user
from app.core.mail import build_password_reset_email, build_verification_email, send_email
from app.models.user import User

router = APIRouter()


class GitHubCodeIn(BaseModel):
    code: str


class GitHubTokenIn(BaseModel):
    access_token: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    github_login: str | None = None


class MeOut(BaseModel):
    id: int
    github_id: int | None = None
    github_login: str | None = None
    email: str | None = None
    avatar_url: str | None = None
    email_verified: bool = False


class RegisterIn(BaseModel):
    email: EmailStr
    password: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


@router.post("/github", response_model=TokenOut)
async def login_with_github(
    body: GitHubCodeIn,
    session: AsyncSession = Depends(get_session),
) -> TokenOut:
    try:
        gh_token = await exchange_github_code(body.code)
        profile = await fetch_github_user(gh_token)
    except OAuthError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    github_id = int(profile["id"])
    result = await session.execute(select(User).where(User.github_id == github_id))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            github_id=github_id,
            github_login=profile["login"],
            email=profile.get("email"),
            avatar_url=profile.get("avatar_url"),
            email_verified=True,  # GitHub OAuth implies email already verified upstream
        )
        session.add(user)
    else:
        user.github_login = profile["login"]
        user.email = profile.get("email")
        user.avatar_url = profile.get("avatar_url")
        user.email_verified = True
    await session.commit()
    await session.refresh(user)

    return TokenOut(access_token=issue_jwt(user.id), user_id=user.id, github_login=user.github_login)


@router.post("/github-token", response_model=TokenOut)
async def login_with_github_token(
    body: GitHubTokenIn,
    session: AsyncSession = Depends(get_session),
) -> TokenOut:
    """Frontend (NextAuth) already exchanged code for access_token. Trust it,
    fetch the GitHub profile, upsert user, return our JWT."""
    try:
        profile = await fetch_github_user(body.access_token)
    except OAuthError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    github_id = int(profile["id"])
    result = await session.execute(select(User).where(User.github_id == github_id))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            github_id=github_id,
            github_login=profile["login"],
            email=profile.get("email"),
            avatar_url=profile.get("avatar_url"),
            email_verified=True,
        )
        session.add(user)
    else:
        user.github_login = profile["login"]
        user.email = profile.get("email")
        user.avatar_url = profile.get("avatar_url")
        user.email_verified = True
    await session.commit()
    await session.refresh(user)

    return TokenOut(access_token=issue_jwt(user.id), user_id=user.id, github_login=user.github_login)


@router.get("/me", response_model=MeOut)
async def me(user: User = Depends(get_current_user)) -> MeOut:
    return MeOut(
        id=user.id,
        github_id=user.github_id,
        github_login=user.github_login,
        email=user.email,
        avatar_url=user.avatar_url,
        email_verified=user.email_verified,
    )


async def _send_verification(user: User) -> bool:
    if not user.email:
        return False
    token = issue_email_verify_token(user.id)
    link = f"{settings.api_public_base}/verify-email?token={token}"
    subject, html, text = build_verification_email(link=link, to_email=user.email)
    return await send_email(to=user.email, subject=subject, html=html, text=text)


@router.post("/register", response_model=TokenOut)
async def register(
    body: RegisterIn,
    session: AsyncSession = Depends(get_session),
) -> TokenOut:
    result = await session.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")
    if len(body.password) < 6:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "password must be at least 6 characters")

    user = User(email=body.email, password_hash=hash_password(body.password), email_verified=False)
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Fire verification email — best-effort. If RESEND_API_KEY is unset, send_email
    # logs a warning and returns False; we don't block registration on it.
    await _send_verification(user)

    return TokenOut(access_token=issue_jwt(user.id), user_id=user.id)


@router.post("/resend-verification")
async def resend_verification(user: User = Depends(get_current_user)) -> dict[str, str]:
    if user.email_verified:
        return {"status": "already_verified"}
    if not user.email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no email on account")
    ok = await _send_verification(user)
    return {"status": "sent" if ok else "skipped_no_email_provider"}


@router.get("/verify-email")
async def verify_email(
    token: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    try:
        user_id = decode_email_verify_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "verification link expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid verification link")

    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    if not user.email_verified:
        user.email_verified = True
        await session.commit()
    return {"status": "verified", "email": user.email or ""}


@router.post("/login", response_model=TokenOut)
async def login(
    body: LoginIn,
    session: AsyncSession = Depends(get_session),
) -> TokenOut:
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None or user.password_hash is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid email or password")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid email or password")
    return TokenOut(access_token=issue_jwt(user.id), user_id=user.id, github_login=user.github_login)


class ForgotPasswordIn(BaseModel):
    email: EmailStr


@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordIn,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Always returns 'ok' to avoid leaking which emails are registered.
    If the user exists and has a password (i.e. not pure GitHub OAuth),
    send a reset link by email."""
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is not None and user.password_hash is not None and user.email:
        token = issue_password_reset_token(user.id)
        link = f"{settings.api_public_base}/reset-password?token={token}"
        subject, html, text = build_password_reset_email(link=link, to_email=user.email)
        await send_email(to=user.email, subject=subject, html=html, text=text)
    return {"status": "ok"}


class ResetPasswordIn(BaseModel):
    token: str
    password: str


@router.post("/reset-password", response_model=TokenOut)
async def reset_password(
    body: ResetPasswordIn,
    session: AsyncSession = Depends(get_session),
) -> TokenOut:
    if len(body.password) < 6:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "password must be at least 6 characters")
    try:
        user_id = decode_password_reset_token(body.token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "reset link expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid reset link")

    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    user.password_hash = hash_password(body.password)
    # Successfully resetting via the email link also implicitly verifies the email,
    # because only the inbox owner could have received the token.
    if user.email and not user.email_verified:
        user.email_verified = True
    await session.commit()
    return TokenOut(access_token=issue_jwt(user.id), user_id=user.id, github_login=user.github_login)
