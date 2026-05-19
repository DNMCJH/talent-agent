"""Resume Rewriter agent: generate STAR bullets tailored to a specific JD."""

from __future__ import annotations

from app.core.llm import call_llm_structured
from app.schemas.agent_models import ImprovementPlan, MatchResult, ResumeBundle

SYSTEM_PROMPT = """You are a resume writing expert for tech internship candidates.

Generate resume project bullets in STAR format (Situation-Task-Action-Result) that:
1. Lead with impact/action verbs (Built, Designed, Implemented, Optimized, Deployed)
2. Include specific technologies from the JD's required skills
3. Quantify where possible; if no real metrics yet, insert [METRIC_PLACEHOLDER] with a note on what to measure
4. Each bullet is 1-2 lines max
5. The stack_line lists technologies in order of JD relevance
6. 3-5 bullets total, ordered by JD relevance

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
