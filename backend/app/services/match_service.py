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
from app.services.embedder import embed_text_async, embed_texts_async


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
    return must_cov, plus_cov, matched_must, missing_must, matched_plus


def _cosine(a: list[float], b: list[float]) -> float:
    # Vectors come pre-normalized from BGE (normalize_embeddings=True), so dot == cosine.
    return sum(x * y for x, y in zip(a, b))


def _semantic_rescue(
    project: ProjectDoc,
    missing: list[str],
    skill_vecs: dict[str, list[float]],
    project_vec: list[float],
    threshold: float = 0.45,
) -> tuple[list[str], list[str]]:
    """Move missing skills to matched if BGE cosine(skill, project) >= threshold.

    Threshold 0.45 calibrated against BGE-zh embeddings of short JD skill names
    (e.g. "Python", "深度学习") vs project stack-summary text. Lower than typical
    BGE thresholds because skill names are very short — they don't pull cosine high
    even when conceptually identical to project content.
    """
    if not missing:
        return [], missing
    rescued: list[str] = []
    still_missing: list[str] = []
    for name in missing:
        vec = skill_vecs.get(name)
        if vec is None:
            still_missing.append(name)
            continue
        if _cosine(vec, project_vec) >= threshold:
            rescued.append(name)
        else:
            still_missing.append(name)
    return rescued, still_missing


async def match_for_user(
    user_id: int,
    raw_jd: str,
    session: AsyncSession,
    *,
    top_k: int = 5,
    language: str = "en",
) -> MatchResult:
    parsed = await parse_jd(raw_jd)

    query_text = " ".join(parsed.keywords_for_search)
    query_vector = await embed_text_async(query_text)

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

    # Pre-compute BGE vectors so semantic rescue is one batch call instead of N small ones.
    # Skill vec: embed the skill name. Project vec: short "stack + topics" string —
    # NOT the full readme, because we want to match against advertised skills, not random
    # text that happens to mention a buzzword once.
    must_names = [s.name for s in parsed.must_skills]
    plus_names = [s.name for s in parsed.plus_skills]
    all_skill_names = list(dict.fromkeys(must_names + plus_names))  # dedupe, preserve order
    skill_vec_list = await embed_texts_async(all_skill_names) if all_skill_names else []
    skill_vecs = dict(zip(all_skill_names, skill_vec_list))

    candidate_docs: dict[int, ProjectDoc] = {}
    for pid in project_ids:
        proj_row = projects_by_id.get(pid)
        if proj_row is None or not proj_row.doc:
            continue
        candidate_docs[pid] = ProjectDoc.model_validate(proj_row.doc)
    project_texts = [
        # Include a README slice so the project vector reflects what the project
        # actually does, not just its tech tags. Cap at 500 chars — enough for the
        # opening pitch, short enough to keep batch encode fast.
        f"{d.name}. Stack: {', '.join(d.stack)}. Topics: {', '.join(d.topics)}. {d.readme[:500]}"
        for d in candidate_docs.values()
    ]
    project_vec_list = await embed_texts_async(project_texts) if project_texts else []
    project_vecs = dict(zip(candidate_docs.keys(), project_vec_list))

    matches: list[Match] = []
    for pid, project in candidate_docs.items():
        must_cov, plus_cov, matched, missing, matched_plus = _score(project, parsed)

        # Semantic rescue: skills that didn't string-match but are conceptually close.
        proj_vec = project_vecs.get(pid)
        rescued_must, missing = (
            _semantic_rescue(project, missing, skill_vecs, proj_vec) if proj_vec else ([], missing)
        )
        if rescued_must:
            matched = matched + rescued_must
            if len(parsed.must_skills):
                must_cov = len(matched) / len(parsed.must_skills)

        # Same rescue for plus skills (against the still-unmatched plus list).
        unmatched_plus = [s for s in plus_names if s not in matched_plus]
        rescued_plus, _ = (
            _semantic_rescue(project, unmatched_plus, skill_vecs, proj_vec) if proj_vec else ([], unmatched_plus)
        )
        if rescued_plus:
            matched_plus = matched_plus + rescued_plus
            if len(parsed.plus_skills):
                plus_cov = len(matched_plus) / len(parsed.plus_skills)

        vector_score = next(
            (p.score for p in points if p.payload and p.payload.get("project_id") == pid),
            0.0,
        )
        # Skill coverage is the strongest signal; vector similarity is the tiebreaker.
        # Weights: must 0.5 / plus 0.3 / vector 0.2. When the JD yielded no
        # must_skills (jd_parser normally forces >=3, so this is a rare vague-JD
        # fallback), must_cov is structurally 0 and would halve every score —
        # redistribute its 0.5 weight onto plus and vector instead.
        vec = vector_score or 0.0
        if parsed.must_skills:
            blended = 0.5 * must_cov + 0.3 * plus_cov + 0.2 * vec
        else:
            blended = 0.6 * plus_cov + 0.4 * vec
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

    lang_instr = (
        "Respond in Chinese (Mandarin)." if language == "zh" else "Respond in English."
    )
    async def _gen_reason(m: Match) -> None:
        m.match_reason = await call_llm(
            system=(
                "Generate a one-sentence explanation of why this project matches the JD. "
                "Be specific about which skills overlap. " + lang_instr
            ),
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
