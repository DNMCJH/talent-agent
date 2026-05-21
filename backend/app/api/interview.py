from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import issue_stream_token
from app.core.db import get_session
from app.core.deps import get_current_user_sse
from app.core.rate_limit import rate_limit_llm
from app.core.sse import SSE_HEADERS, pop_stream_payload, stage_stream_payload, wrap_sse
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
# Two-step flow: the client POSTs the request body to a `prepare` endpoint
# (normal Bearer auth + rate limit), which stages the payload server-side and
# returns an opaque stream_id plus a short-lived stream token. The SSE GET then
# carries only `stream_id` + `token` — no JD text or interview answers in the
# URL, so nothing sensitive lands in access logs or browser history.


@router.post("/start/stream/prepare")
async def start_stream_prepare(
    body: StartInterviewIn,
    user: User = Depends(rate_limit_llm),
) -> dict:
    stream_id = await stage_stream_payload(user.id, body.model_dump())
    return {"stream_id": stream_id, "stream_token": issue_stream_token(user.id)}


@router.get("/start/stream")
async def start_stream(
    stream_id: str = Query(...),
    user: User = Depends(get_current_user_sse),
) -> StreamingResponse:
    payload = await pop_stream_payload(stream_id, user.id)
    body = StartInterviewIn.model_validate(payload)
    ids = body.project_ids or ([body.project_id] if body.project_id else [])
    return StreamingResponse(
        wrap_sse(start_interview_stream(
            user_id=user.id,
            project_ids=ids,
            interview_type=body.interview_type,
            mode=body.mode,
            raw_jd=body.raw_jd,
            language=body.language,
            resume_context=body.resume_context,
        )),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post("/turn/stream/prepare")
async def turn_stream_prepare(
    body: TurnIn,
    user: User = Depends(rate_limit_llm),
) -> dict:
    stream_id = await stage_stream_payload(user.id, body.model_dump())
    return {"stream_id": stream_id, "stream_token": issue_stream_token(user.id)}


@router.get("/turn/stream")
async def turn_stream(
    stream_id: str = Query(...),
    user: User = Depends(get_current_user_sse),
) -> StreamingResponse:
    payload = await pop_stream_payload(stream_id, user.id)
    body = TurnIn.model_validate(payload)
    return StreamingResponse(
        wrap_sse(take_turn_stream(
            user_id=user.id,
            session_id=body.session_id,
            candidate_message=body.candidate_message,
        )),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
