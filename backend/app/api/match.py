from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.rate_limit import rate_limit_llm
from app.models.user import User
from app.schemas.agent_models import CoverLetter, ImprovementPlan, MatchResult
from app.services.cover_letter import generate_cover_letter
from app.services.improvement_planner import generate_improvements
from app.services.match_service import match_for_user

router = APIRouter()


class MatchIn(BaseModel):
    # JDs in the wild fit comfortably under 20K chars. Bound prevents a single
    # request from ballooning the parser, embedder, Redis stage, and paid LLM calls.
    raw_jd: str = Field(..., min_length=1, max_length=20_000)
    top_k: int = Field(default=5, ge=1, le=10)
    language: str = Field(default="en", pattern="^(en|zh)$")


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
    return await generate_improvements(match_result, language=body.language)


@router.post("/cover-letter", response_model=CoverLetter)
async def run_cover_letter(
    body: MatchIn,
    user: User = Depends(rate_limit_llm),
    session: AsyncSession = Depends(get_session),
) -> CoverLetter:
    """Draft a JD-tailored cover letter from the user's best-matching projects."""
    match_result = await match_for_user(
        user_id=user.id,
        raw_jd=body.raw_jd,
        session=session,
        top_k=body.top_k,
        language=body.language,
    )
    return await generate_cover_letter(match_result, language=body.language)
