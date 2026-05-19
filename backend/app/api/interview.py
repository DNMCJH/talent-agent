from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import get_current_user
from app.models.user import User
from app.services.interview_service import start_interview, take_turn

router = APIRouter()


class StartInterviewIn(BaseModel):
    project_id: int
    raw_jd: str
    mode: str = "tech"  # 'tech' | 'stress' | 'behavior'


class TurnIn(BaseModel):
    session_id: str
    candidate_message: str


@router.post("/start")
async def start(
    body: StartInterviewIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await start_interview(
        user_id=user.id,
        project_id=body.project_id,
        mode=body.mode,
        raw_jd=body.raw_jd,
        session=session,
    )


@router.post("/turn")
async def turn(
    body: TurnIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await take_turn(
        user_id=user.id,
        session_id=body.session_id,
        candidate_message=body.candidate_message,
        session=session,
    )
