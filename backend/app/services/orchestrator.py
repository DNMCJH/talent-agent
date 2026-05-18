"""Pipeline orchestrator: connects all agents into a coherent workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from app.agents.improver import generate_improvements
from app.agents.interviewer import init_interview
from app.agents.matcher import match_projects
from app.agents.parser import parse_jd
from app.agents.rewriter import rewrite_resume
from app.core.config import settings
from app.schemas.agent_models import (
    ImprovementPlan,
    InterviewSession,
    MatchResult,
    ParsedJD,
    ResumeBundle,
)

Intent = Literal["match_only", "full_loop", "interview_only", "improve_only", "resume_only"]


@dataclass
class Session:
    raw_jd: str
    intent: Intent = "full_loop"
    parsed: ParsedJD | None = None
    match: MatchResult | None = None
    plan: ImprovementPlan | None = None
    resume: ResumeBundle | None = None
    interview: InterviewSession | None = None
    errors: list[str] = field(default_factory=list)


_qdrant: QdrantClient | None = None
_embedder: SentenceTransformer | None = None


def get_qdrant() -> QdrantClient:
    """Process-wide Qdrant client. Caller owns the lifecycle via close_qdrant()."""
    global _qdrant
    if _qdrant is None:
        if settings.qdrant_url:
            _qdrant = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
        else:
            from pathlib import Path
            Path(settings.qdrant_local_path).mkdir(parents=True, exist_ok=True)
            _qdrant = QdrantClient(path=settings.qdrant_local_path)
    return _qdrant


def get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        import os
        os.environ.setdefault("TQDM_DISABLE", "1")
        _embedder = SentenceTransformer(settings.embed_model, device=settings.embed_device)
    return _embedder


def close_qdrant() -> None:
    """Explicitly close the Qdrant client. Long-running hosts (Streamlit) should NOT call this between requests."""
    global _qdrant
    if _qdrant is not None:
        _qdrant.close()
        _qdrant = None


async def run_pipeline(
    raw_jd: str,
    intent: Intent = "full_loop",
    *,
    qdrant: QdrantClient | None = None,
    embedder: SentenceTransformer | None = None,
) -> Session:
    """Run the agent pipeline. Pass cached qdrant/embedder for long-running hosts."""
    session = Session(raw_jd=raw_jd, intent=intent)

    session.parsed = await parse_jd(raw_jd)

    session.match = await match_projects(
        session.parsed,
        qdrant or get_qdrant(),
        embedder or get_embedder(),
    )

    if intent in ("full_loop", "improve_only"):
        session.plan = await generate_improvements(session.match)

    if intent in ("full_loop", "resume_only"):
        session.resume = await rewrite_resume(session.match, session.plan)

    if intent in ("full_loop", "interview_only"):
        best_project = session.match.overall_best.project
        session.interview = await init_interview(session.parsed, best_project)

    return session
