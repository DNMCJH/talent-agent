from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.rate_limit import rate_limit_llm
from app.models.user import User
from app.services.interview_service import start_interview, take_turn

router = APIRouter()


class StartInterviewIn(BaseModel):
    project_ids: list[int] = []
    project_id: int | None = None
    raw_jd: str = ""
    mode: str = "tech"  # 'tech' | 'stress' | 'behavior' | 'comprehensive'
    interview_type: str = "targeted"  # 'targeted' | 'comprehensive'
    language: str = "en"  # 'zh' | 'en'


class TurnIn(BaseModel):
    session_id: str
    candidate_message: str


@router.post("/start")
async def start(
    body: StartInterviewIn,
    user: User = Depends(rate_limit_llm),
    session: AsyncSession = Depends(get_session),
) -> dict:
    ids = body.project_ids or ([body.project_id] if body.project_id else [])
    return await start_interview(
        user_id=user.id,
        project_ids=ids,
        interview_type=body.interview_type,
        mode=body.mode,
        raw_jd=body.raw_jd,
        language=body.language,
        session=session,
    )


@router.post("/turn")
async def turn(
    body: TurnIn,
    user: User = Depends(rate_limit_llm),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await take_turn(
        user_id=user.id,
        session_id=body.session_id,
        candidate_message=body.candidate_message,
        session=session,
    )
