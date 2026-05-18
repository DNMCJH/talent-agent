from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    OAuthError,
    exchange_github_code,
    fetch_github_user,
    issue_jwt,
)
from app.core.db import get_session
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter()


class GitHubCodeIn(BaseModel):
    code: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    github_login: str


class MeOut(BaseModel):
    id: int
    github_id: int
    github_login: str
    email: str | None = None
    avatar_url: str | None = None


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


@router.get("/me", response_model=MeOut)
async def me(user: User = Depends(get_current_user)) -> MeOut:
    return MeOut(
        id=user.id,
        github_id=user.github_id,
        github_login=user.github_login,
        email=user.email,
        avatar_url=user.avatar_url,
    )
