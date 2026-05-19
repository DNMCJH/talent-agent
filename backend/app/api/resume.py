from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.rewriter import rewrite_resume
from app.core.db import get_session
from app.core.deps import get_current_user
from app.models.project import Project
from app.models.user import User
from app.schemas.agent_models import (
    Match,
    MatchResult,
    ProjectDoc,
    ResumeBundle,
)
from app.services.match_service import match_for_user

router = APIRouter()


class ResumeIn(BaseModel):
    project_id: int
    raw_jd: str


@router.post("", response_model=ResumeBundle)
async def generate_resume(
    body: ResumeIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ResumeBundle:
    """Score the requested project against the JD, then generate STAR-format resume bullets.
    Uses match_for_user (with user_id filter) to score this specific project, not a global search."""
    proj = await session.get(Project, body.project_id)
    if proj is None or proj.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    if not proj.doc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "project has no indexed doc"
        )

    full_match = await match_for_user(
        user_id=user.id, raw_jd=body.raw_jd, session=session, top_k=10
    )
    project_doc = ProjectDoc.model_validate(proj.doc)
    chosen = next(
        (m for m in full_match.matches if m.project.name == project_doc.name), None
    )
    if chosen is None:
        # No skill overlap — generate bullets anyway, with empty matched_skills.
        chosen = Match(
            project=project_doc,
            coverage=0.0, plus_coverage=0.0, weighted_score=0.0,
            matched_skills=[], missing_skills=[s.name for s in full_match.jd.must_skills],
        )

    single = MatchResult(jd=full_match.jd, matches=[chosen], overall_best=chosen)
    return await rewrite_resume(single, plan=None)
