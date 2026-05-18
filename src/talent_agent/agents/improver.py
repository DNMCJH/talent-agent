"""Improver agent: turn match gaps into actionable PR-level tasks."""

from __future__ import annotations

from talent_agent.llm import call_llm_structured
from talent_agent.models import ImprovementPlan, MatchResult

SYSTEM_PROMPT = """You are a senior engineering mentor helping an intern candidate prepare for interviews.

Given a project and its skill gaps relative to a target JD, generate 3-5 concrete improvement tasks that:
1. Each task addresses 1-2 missing skills from the JD
2. Each task is completable in 1-7 days
3. Tasks are ordered by ROI (interview impact per effort day)
4. Deliverables are specific and verifiable (not vague like "improve performance")
5. Implementation hints give enough direction to start without hand-holding
6. Resume impact describes what the candidate can write on their resume after completing the task

Focus on changes that are:
- Demonstrable in an interview (can show code, explain design decisions)
- Relevant to the target role (not generic improvements)
- Buildable on top of the existing project (not rewrites)
"""


async def generate_improvements(match_result: MatchResult) -> ImprovementPlan:
    best = match_result.overall_best
    context = f"""Target JD: {match_result.jd.role} at {match_result.jd.company}
Must-have skills: {[s.name for s in match_result.jd.must_skills]}
Plus skills: {[s.name for s in match_result.jd.plus_skills]}

Best matching project: {best.project.name}
Current stack: {best.project.stack}
Topics: {best.project.topics}
Coverage: {best.coverage:.0%}
Matched skills: {best.matched_skills}
Missing skills: {best.missing_skills}
Has Docker: {best.project.has_dockerfile}
Has tests: {best.project.has_tests}
Has deployment: {best.project.deployment_signal}

README excerpt:
{best.project.readme[:2000]}"""

    return await call_llm_structured(
        system=SYSTEM_PROMPT,
        user_message=context,
        output_schema=ImprovementPlan,
    )
