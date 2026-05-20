from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.rate_limit import rate_limit_llm, rate_limit_llm_sse
from app.core.sse import SSE_HEADERS, wrap_sse
from app.models.user import User
from app.services.interview_service import (
    start_interview,
    start_interview_stream,
    take_turn,
    take_turn_stream,
)

router = APIRouter()


class StartInterviewIn(BaseModel):
    project_ids: list[int] = []
    project_id: int | None = None
    raw_jd: str = ""
    mode: str = "tech"  # 'tech' | 'stress' | 'behavior' | 'comprehensive'
    interview_type: str = "targeted"  # 'targeted' | 'comprehensive'
    language: str = "en"  # 'zh' | 'en'
    resume_context: str = ""  # optional: candidate background from parsed resume


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
        resume_context=body.resume_context,
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


# ---------- SSE streaming endpoints ----------
#
# EventSource cannot send Authorization headers, so auth comes from `?token=`
# query param. Body params are also passed as query params for the same reason.


@router.get("/start/stream")
async def start_stream(
    project_ids: str = Query(default=""),  # comma-separated IDs
    raw_jd: str = Query(default=""),
    mode: str = Query(default="tech"),
    interview_type: str = Query(default="targeted"),
    language: str = Query(default="en"),
    resume_context: str = Query(default=""),
    user: User = Depends(rate_limit_llm_sse),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    ids = [int(x) for x in project_ids.split(",") if x.strip()]
    return StreamingResponse(
        wrap_sse(start_interview_stream(
            user_id=user.id,
            project_ids=ids,
            interview_type=interview_type,
            mode=mode,
            raw_jd=raw_jd,
            language=language,
            resume_context=resume_context,
            session=session,
        )),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.get("/turn/stream")
async def turn_stream(
    session_id: str = Query(...),
    candidate_message: str = Query(...),
    user: User = Depends(rate_limit_llm_sse),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    return StreamingResponse(
        wrap_sse(take_turn_stream(
            user_id=user.id,
            session_id=session_id,
            candidate_message=candidate_message,
            session=session,
        )),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
