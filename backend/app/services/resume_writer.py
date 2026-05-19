"""Resume Rewriter agent: generate STAR bullets tailored to a specific JD."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.core.llm import call_llm_structured
from app.schemas.agent_models import ImprovementPlan, Match, MatchResult, ResumeBundle

SYSTEM_PROMPT = """You are a resume writing expert for tech internship candidates.

Generate resume project bullets in STAR format (Situation-Task-Action-Result) that:
1. Lead with impact/action verbs (Built, Designed, Implemented, Optimized, Deployed)
2. Include specific technologies from the JD's required skills
3. Each bullet is 1-2 lines max
4. The stack_line lists technologies in order of JD relevance
5. 3-5 bullets total, ordered by JD relevance

STRICT FACTUAL RULES — violations make the resume worthless:
- NEVER invent quantitative metrics. No "提升 50%", no "支持 1000 QPS", no "处理 10 万用户".
  If the README does not contain a real number, do NOT make one up and do NOT insert any
  placeholder like [METRIC_PLACEHOLDER] or [TODO]. Just describe what was built and why
  it matters, qualitatively.
- NEVER name frameworks the project does not actually use. If README does not mention
  LangChain / LangGraph / Celery / Kafka / Redis, do NOT claim the project uses them.
  Stick to the Stack list and what the README plainly states.
- NEVER invent architecture patterns that are not in the README (no fake "多智能体协作",
  no fake "RAG pipeline" unless the README really describes one).

When you have no numbers, use concrete qualitative anchors instead:
  GOOD: "设计基于 FastAPI 的多租户向量检索后端，按 user_id 在 Qdrant payload 层做过滤隔离"
  BAD:  "设计基于 FastAPI 的多租户向量检索后端，QPS 提升 [METRIC_PLACEHOLDER]"

Write for a candidate who actually built this project (not someone who cloned it).
Tailor language to match the JD's tone (enterprise vs startup, English vs Chinese).
"""


async def rewrite_resume(
    match_result: MatchResult,
    plan: ImprovementPlan | None = None,
    language: str = "en",
) -> ResumeBundle:
    best = match_result.overall_best
    jd = match_result.jd

    context = f"""Target role: {jd.role} at {jd.company}
Must-have skills: {[s.name for s in jd.must_skills]}
Plus skills: {[s.name for s in jd.plus_skills]}
JD language: {jd.language}

Project: {best.project.name}
Stack: {best.project.stack}
Topics: {best.project.topics}
README excerpt:
{best.project.readme[:1500]}

Matched skills: {best.matched_skills}
Missing skills (candidate is working on these): {best.missing_skills}"""

    if plan:
        completed_tasks = [t.title for t in plan.tasks[:3]]
        context += f"\n\nImprovement tasks completed/planned: {completed_tasks}"

    lang_instr = (
        "\n\nIMPORTANT: Write all bullets and the project_title in Chinese (Mandarin). "
        "Keep technology names (e.g. FastAPI, Docker) in original English casing."
        if language == "zh"
        else "\n\nIMPORTANT: Write all bullets and the project_title in English."
    )
    return await call_llm_structured(
        system=SYSTEM_PROMPT + lang_instr,
        user_message=context,
        output_schema=ResumeBundle,
    )


def _build_single_match_result(jd_parsed, match: Match) -> MatchResult:
    """Wrap one Match in a MatchResult so we can reuse rewrite_resume per project."""
    return MatchResult(jd=jd_parsed, matches=[match], overall_best=match)


async def rewrite_resume_multi(
    match_result: MatchResult,
    *,
    language: str = "en",
    max_projects: int = 5,
) -> list[ResumeBundle]:
    """Generate one resume bundle per matched project, in match-ranking order.

    Sequential (not parallel) by design — five LLM calls in parallel can hit
    rate limits and the user sees progress better when bundles arrive one by one
    via the streaming variant.
    """
    bundles: list[ResumeBundle] = []
    for m in match_result.matches[:max_projects]:
        single = _build_single_match_result(match_result.jd, m)
        bundle = await rewrite_resume(single, plan=None, language=language)
        bundles.append(bundle)
    return bundles


async def rewrite_resume_multi_stream(
    match_result: MatchResult,
    *,
    language: str = "en",
    max_projects: int = 5,
) -> AsyncIterator[dict[str, Any]]:
    """Yield one event per project as it finishes, plus a final done event.

    Event shapes:
      {"type": "progress", "index": 0, "total": 3, "project_name": "..."}
      {"type": "bundle",   "index": 0, "bundle": {...ResumeBundle...}}
      {"type": "done",     "total": 3}
    """
    selected = match_result.matches[:max_projects]
    total = len(selected)
    for i, m in enumerate(selected):
        yield {
            "type": "progress",
            "index": i,
            "total": total,
            "project_name": m.project.name,
        }
        single = _build_single_match_result(match_result.jd, m)
        bundle = await rewrite_resume(single, plan=None, language=language)
        yield {
            "type": "bundle",
            "index": i,
            "project_name": m.project.name,
            "bundle": bundle.model_dump(),
        }
    yield {"type": "done", "total": total}
