"""Matcher agent: find best-matching projects for a parsed JD."""

from __future__ import annotations

from qdrant_client import QdrantClient

from app.core.config import settings
from app.core.llm import call_llm
from app.schemas.agent_models import Match, MatchResult, ParsedJD, ProjectDoc


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


def _compute_scores(project: ProjectDoc, jd: ParsedJD):
    """Return (must_coverage, plus_coverage, weighted_score, matched_must, missing_must, matched_plus)."""
    project_skills_norm = {_normalize_skill(s) for s in project.stack + project.topics}

    matched_must, missing_must = _match_skills(jd.must_skills, project_skills_norm)
    matched_plus, _ = _match_skills(jd.plus_skills, project_skills_norm)

    must_total = len(jd.must_skills)
    plus_total = len(jd.plus_skills)

    must_cov = len(matched_must) / must_total if must_total else 0.0
    plus_cov = len(matched_plus) / plus_total if plus_total else 0.0

    # If no plus_skills, weighted == must. If plus exist, blend 0.7/0.3.
    if plus_total == 0:
        weighted = must_cov
    else:
        weighted = 0.7 * must_cov + 0.3 * plus_cov

    return must_cov, plus_cov, weighted, matched_must, missing_must, matched_plus


async def match_projects(jd: ParsedJD, qdrant: QdrantClient, embedder) -> MatchResult:
    query_text = " ".join(jd.keywords_for_search)
    query_vector = embedder.encode(query_text).tolist()

    results = qdrant.query_points(
        collection_name=settings.qdrant_collection_projects,
        query=query_vector,
        limit=20,
    )

    matches: list[Match] = []
    for point in results.points:
        project = ProjectDoc.model_validate(point.payload)
        must_cov, plus_cov, weighted, matched, missing, matched_plus = _compute_scores(project, jd)

        if matched or matched_plus:
            bonus = [s for s in project.stack if _normalize_skill(s) not in
                     {_normalize_skill(sk.name) for sk in jd.must_skills + jd.plus_skills}]
            matches.append(Match(
                project=project,
                coverage=must_cov,
                plus_coverage=plus_cov,
                weighted_score=weighted,
                matched_skills=matched,
                missing_skills=missing,
                matched_plus_skills=matched_plus,
                bonus_skills=bonus[:5],
            ))

    matches.sort(key=lambda m: (-m.weighted_score, -m.project.deployment_signal))
    top_matches = matches[:5]

    for m in top_matches:
        m.match_reason = await call_llm(
            system="Generate a one-sentence explanation of why this project matches the JD. Be specific about which skills overlap.",
            user_message=f"JD role: {jd.role} at {jd.company}\nRequired: {[s.name for s in jd.must_skills]}\nProject: {m.project.name}\nStack: {m.project.stack}\nTopics: {m.project.topics}",
            max_tokens=150,
        )

    if not top_matches:
        dummy = Match(
            project=ProjectDoc(name="(no match)", path="", readme="", stack=[]),
            coverage=0.0,
            plus_coverage=0.0,
            weighted_score=0.0,
            matched_skills=[],
            missing_skills=[s.name for s in jd.must_skills],
        )
        top_matches = [dummy]

    return MatchResult(jd=jd, matches=top_matches, overall_best=top_matches[0])
