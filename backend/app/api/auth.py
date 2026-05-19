from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    OAuthError,
    exchange_github_code,
    fetch_github_user,
    issue_jwt,
    hash_password,
    verify_password,
)
from app.core.db import get_session
from app.core.deps import get_current_user
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
        )
        session.add(user)
    else:
        user.github_login = profile["login"]
        user.email = profile.get("email")
        user.avatar_url = profile.get("avatar_url")
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
        )
        session.add(user)
    else:
        user.github_login = profile["login"]
        user.email = profile.get("email")
        user.avatar_url = profile.get("avatar_url")
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
    )


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

    user = User(email=body.email, password_hash=hash_password(body.password))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return TokenOut(access_token=issue_jwt(user.id), user_id=user.id)


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
