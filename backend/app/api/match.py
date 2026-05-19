from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.agent_models import MatchResult
from app.services.match_service import match_for_user

router = APIRouter()


class MatchIn(BaseModel):
    raw_jd: str
    top_k: int = 5


@router.post("", response_model=MatchResult)
async def run_match(
    body: MatchIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MatchResult:
    return await match_for_user(
        user_id=user.id, raw_jd=body.raw_jd, session=session, top_k=body.top_k
    )
