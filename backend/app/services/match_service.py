"""User-aware match pipeline.

Replaces the Streamlit-era orchestrator path for multi-tenant SaaS. Differences:
- All Qdrant searches go through vector_store (user_id payload filter enforced server-side).
- Project payloads are fetched fresh from Postgres, not cached in Qdrant — Qdrant only
  holds (vector + small payload for filtering); the authoritative ProjectDoc lives in Postgres.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.jd_parser import parse_jd
from app.core.llm import call_llm
from app.models.project import Project
from app.schemas.agent_models import Match, MatchResult, ParsedJD, ProjectDoc
from app.services import vector_store
from app.services.embedder import embed_text


def _normalize_skill(name: str) -> str:
    return name.lower().strip().replace("-", "").replace("_", "").replace(" ", "")


def _match_skills(skills, project_skills_norm: set[str]) -> tuple[list[str], list[str]]:
    matched, missing = [], []
    for s in skills:
        variants = {_normalize_skill(s.name)} | {_normalize_skill(a) for a in s.aliases}
        if variants & project_skills_norm:
            matched.append(s.name)
        else:
            missing.append(s.name)
    return matched, missing


def _score(project: ProjectDoc, jd: ParsedJD):
    project_skills_norm = {_normalize_skill(s) for s in project.stack + project.topics}
    matched_must, missing_must = _match_skills(jd.must_skills, project_skills_norm)
    matched_plus, _ = _match_skills(jd.plus_skills, project_skills_norm)

    must_total = len(jd.must_skills)
    plus_total = len(jd.plus_skills)
    must_cov = len(matched_must) / must_total if must_total else 0.0
    plus_cov = len(matched_plus) / plus_total if plus_total else 0.0
    weighted = must_cov if plus_total == 0 else 0.7 * must_cov + 0.3 * plus_cov
    return must_cov, plus_cov, weighted, matched_must, missing_must, matched_plus


async def match_for_user(
    user_id: int,
    raw_jd: str,
    session: AsyncSession,
    *,
    top_k: int = 5,
) -> MatchResult:
    parsed = await parse_jd(raw_jd)

    query_text = " ".join(parsed.keywords_for_search)
    query_vector = embed_text(query_text)

    points = await vector_store.search_projects(
        user_id=user_id, query_vector=query_vector, limit=20
    )
    if not points:
        empty = Match(
            project=ProjectDoc(name="(no projects)", path="", readme="", stack=[]),
            coverage=0.0, plus_coverage=0.0, weighted_score=0.0,
            matched_skills=[], missing_skills=[s.name for s in parsed.must_skills],
        )
        return MatchResult(jd=parsed, matches=[empty], overall_best=empty)

    project_ids = [p.payload.get("project_id") for p in points if p.payload]
    project_ids = [pid for pid in project_ids if pid is not None]

    rows = await session.execute(
        select(Project).where(Project.user_id == user_id, Project.id.in_(project_ids))
    )
    projects_by_id = {p.id: p for p in rows.scalars()}

    matches: list[Match] = []
    for pid in project_ids:
        proj_row = projects_by_id.get(pid)
        if proj_row is None or not proj_row.doc:
            continue
        project = ProjectDoc.model_validate(proj_row.doc)
        must_cov, plus_cov, weighted, matched, missing, matched_plus = _score(project, parsed)
        # Include vector similarity from Qdrant as a signal
        vector_score = next(
            (p.score for p in points if p.payload and p.payload.get("project_id") == pid),
            0.0,
        )
        # Blend: 50% skill coverage + 30% plus coverage + 20% vector similarity
        blended = 0.5 * must_cov + 0.3 * plus_cov + 0.2 * (vector_score or 0.0)
        if matched or matched_plus or (vector_score and vector_score > 0.5):
            bonus = [
                s for s in project.stack
                if _normalize_skill(s) not in
                   {_normalize_skill(sk.name) for sk in parsed.must_skills + parsed.plus_skills}
            ]
            matches.append(Match(
                project=project,
                project_id=pid,
                coverage=must_cov,
                plus_coverage=plus_cov,
                weighted_score=round(blended, 3),
                matched_skills=matched,
                missing_skills=missing,
                matched_plus_skills=matched_plus,
                bonus_skills=bonus[:5],
            ))

    matches.sort(key=lambda m: (-m.weighted_score, -int(m.project.deployment_signal)))
    top = matches[:top_k]

    async def _gen_reason(m: Match) -> None:
        m.match_reason = await call_llm(
            system="Generate a one-sentence explanation of why this project matches the JD. Be specific about which skills overlap.",
            user_message=(
                f"JD role: {parsed.role} at {parsed.company}\n"
                f"Required: {[s.name for s in parsed.must_skills]}\n"
                f"Project: {m.project.name}\nStack: {m.project.stack}\nTopics: {m.project.topics}"
            ),
            max_tokens=150,
        )

    if top:
        await asyncio.gather(*[_gen_reason(m) for m in top])

    if not top:
        empty = Match(
            project=ProjectDoc(name="(no match)", path="", readme="", stack=[]),
            coverage=0.0, plus_coverage=0.0, weighted_score=0.0,
            matched_skills=[], missing_skills=[s.name for s in parsed.must_skills],
        )
        top = [empty]

    return MatchResult(jd=parsed, matches=top, overall_best=top[0])
