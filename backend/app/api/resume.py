from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.jd_parser import parse_jd
from app.services.resume_writer import rewrite_resume, rewrite_resume_multi_stream
from app.core.auth import issue_stream_token
from app.core.db import _get_sessionmaker, get_session
from app.core.deps import get_current_user_sse
from app.core.rate_limit import rate_limit_llm
from app.core.sse import SSE_HEADERS, pop_stream_payload, stage_stream_payload, wrap_sse
from app.models.project import Project
from app.models.user import User
from app.schemas.agent_models import (
    Match,
    MatchResult,
    ProjectDoc,
    ResumeBundle,
)
from app.services.match_service import _score

router = APIRouter()


class ResumeIn(BaseModel):
    project_id: int
    raw_jd: str
    language: str = "en"


def _score_project(proj_doc: ProjectDoc, parsed, project_id: int) -> Match:
    must_cov, plus_cov, weighted, matched, missing, matched_plus = _score(proj_doc, parsed)
    return Match(
        project=proj_doc,
        project_id=project_id,
        coverage=must_cov,
        plus_coverage=plus_cov,
        weighted_score=weighted,
        matched_skills=matched,
        missing_skills=missing,
        matched_plus_skills=matched_plus,
    )


@router.post("", response_model=ResumeBundle)
async def generate_resume(
    body: ResumeIn,
    user: User = Depends(rate_limit_llm),
    session: AsyncSession = Depends(get_session),
) -> ResumeBundle:
    proj = await session.get(Project, body.project_id)
    if proj is None or proj.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    if not proj.doc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "project has no indexed doc"
        )

    parsed = await parse_jd(body.raw_jd)
    project_doc = ProjectDoc.model_validate(proj.doc)
    chosen = _score_project(project_doc, parsed, body.project_id)
    single = MatchResult(jd=parsed, matches=[chosen], overall_best=chosen)
    return await rewrite_resume(single, plan=None, language=body.language)


async def _multi_resume_events(
    user_id: int,
    project_ids: list[int],
    raw_jd: str,
    language: str,
) -> AsyncIterator[dict[str, Any]]:
    """Opens its own DB session: the request-scoped session is already closed by
    the time this StreamingResponse generator runs."""
    async with _get_sessionmaker()() as session:
        async for event in _multi_resume_events_impl(
            user_id, project_ids, raw_jd, language, session
        ):
            yield event


async def _multi_resume_events_impl(
    user_id: int,
    project_ids: list[int],
    raw_jd: str,
    language: str,
    session: AsyncSession,
) -> AsyncIterator[dict[str, Any]]:
    if not project_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no projects selected")
    rows = await session.execute(
        select(Project).where(Project.user_id == user_id, Project.id.in_(project_ids))
    )
    projects_by_id = {p.id: p for p in rows.scalars()}
    missing = [pid for pid in project_ids if pid not in projects_by_id]
    if missing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"projects not found: {missing}")

    parsed = await parse_jd(raw_jd)
    # Preserve the user-supplied order so the UI matches what they selected.
    matches: list[Match] = []
    for pid in project_ids:
        proj = projects_by_id[pid]
        if not proj.doc:
            continue
        project_doc = ProjectDoc.model_validate(proj.doc)
        matches.append(_score_project(project_doc, parsed, pid))

    if not matches:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "selected projects have no indexed docs — re-import them",
        )

    overall = matches[0]
    match_result = MatchResult(jd=parsed, matches=matches, overall_best=overall)
    async for event in rewrite_resume_multi_stream(
        match_result, language=language, max_projects=len(matches)
    ):
        yield event


class MultiResumeIn(BaseModel):
    project_ids: list[int]
    raw_jd: str
    language: str = "en"


@router.post("/multi/stream/prepare")
async def generate_resume_multi_prepare(
    body: MultiResumeIn,
    user: User = Depends(rate_limit_llm),
) -> dict:
    """Stage the resume request server-side (see app.core.sse). The SSE GET then
    carries only an opaque id, keeping the JD text out of the URL / access logs."""
    stream_id = await stage_stream_payload(user.id, body.model_dump())
    return {"stream_id": stream_id, "stream_token": issue_stream_token(user.id)}


@router.get("/multi/stream")
async def generate_resume_multi_stream(
    stream_id: str = Query(...),
    user: User = Depends(get_current_user_sse),
) -> StreamingResponse:
    payload = await pop_stream_payload(stream_id, user.id)
    body = MultiResumeIn.model_validate(payload)
    return StreamingResponse(
        wrap_sse(_multi_resume_events(
            user_id=user.id,
            project_ids=body.project_ids,
            raw_jd=body.raw_jd,
            language=body.language,
        )),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
