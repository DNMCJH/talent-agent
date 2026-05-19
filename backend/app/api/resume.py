from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.jd_parser import parse_jd
from app.services.resume_writer import rewrite_resume, rewrite_resume_multi_stream
from app.core.db import get_session
from app.core.rate_limit import rate_limit_llm, rate_limit_llm_sse
from app.core.sse import SSE_HEADERS, wrap_sse
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


@router.get("/multi/stream")
async def generate_resume_multi_stream(
    project_ids: str = Query(...),  # comma-separated IDs
    raw_jd: str = Query(...),
    language: str = Query(default="en"),
    user: User = Depends(rate_limit_llm_sse),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    ids = [int(x) for x in project_ids.split(",") if x.strip()]
    return StreamingResponse(
        wrap_sse(_multi_resume_events(
            user_id=user.id,
            project_ids=ids,
            raw_jd=raw_jd,
            language=language,
            session=session,
        )),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
