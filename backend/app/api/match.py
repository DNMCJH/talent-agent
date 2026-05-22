from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.rate_limit import rate_limit_llm
from app.models.user import User
from app.schemas.agent_models import ImprovementPlan, MatchResult
from app.services.improvement_planner import generate_improvements
from app.services.match_service import match_for_user

router = APIRouter()


class MatchIn(BaseModel):
    raw_jd: str
    top_k: int = 5
    language: str = "en"


@router.post("", response_model=MatchResult)
async def run_match(
    body: MatchIn,
    user: User = Depends(rate_limit_llm),
    session: AsyncSession = Depends(get_session),
) -> MatchResult:
    return await match_for_user(
        user_id=user.id,
        raw_jd=body.raw_jd,
        session=session,
        top_k=body.top_k,
        language=body.language,
    )


@router.post("/improvement", response_model=ImprovementPlan)
async def run_improvement(
    body: MatchIn,
    user: User = Depends(rate_limit_llm),
    session: AsyncSession = Depends(get_session),
) -> ImprovementPlan:
    """Turn the best-matching project's skill gaps into PR-level tasks.

    Re-runs the match server-side so the planner gets the full ProjectDoc
    (readme, topics, signals) — the frontend's MatchResult is stripped.
    """
    match_result = await match_for_user(
        user_id=user.id,
        raw_jd=body.raw_jd,
        session=session,
        top_k=body.top_k,
        language=body.language,
    )
    return await generate_improvements(match_result)
