from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.jd_parser import parse_jd
from app.services.resume_writer import rewrite_resume
from app.core.db import get_session
from app.core.rate_limit import rate_limit_llm
from app.models.project import Project
from app.models.user import User
from app.schemas.agent_models import (
    Match,
    MatchResult,
    ProjectDoc,
    ResumeBundle,
)
from app.services.match_service import _normalize_skill, _match_skills, _score

router = APIRouter()


class ResumeIn(BaseModel):
    project_id: int
    raw_jd: str


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
    must_cov, plus_cov, weighted, matched, missing, matched_plus = _score(project_doc, parsed)

    chosen = Match(
        project=project_doc,
        project_id=body.project_id,
        coverage=must_cov,
        plus_coverage=plus_cov,
        weighted_score=weighted,
        matched_skills=matched,
        missing_skills=missing,
        matched_plus_skills=matched_plus,
    )

    single = MatchResult(jd=parsed, matches=[chosen], overall_best=chosen)
    return await rewrite_resume(single, plan=None)
