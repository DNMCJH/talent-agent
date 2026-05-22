"""Cover letter writer: draft a JD-tailored cover letter from match results."""

from __future__ import annotations

from app.core.llm import call_llm_structured
from app.schemas.agent_models import CoverLetter, MatchResult

SYSTEM_PROMPT = """You are a cover letter writer for tech internship/new-grad candidates.

Given a target JD and the candidate's best-matching projects, draft a cover letter that:
1. recipient — a salutation line (no real name known, address the team/hiring manager)
2. paragraphs — 3 short paragraphs:
   - why this role/company (tie to the JD's focus, concrete not generic)
   - what the candidate brings (cite 1-2 real projects and the skills they prove)
   - a brief close on fit and eagerness
3. closing — a sign-off line

STRICT RULES:
- Use ONLY skills and facts present in the project data. Never invent metrics,
  frameworks, or experience the projects do not show.
- No filler ("I am writing to express my strong interest..."). Lead with substance.
- Keep each paragraph 2-4 sentences. The whole letter should read in under a minute.
- Confident but not arrogant; concrete over adjectives.
"""


async def generate_cover_letter(
    match_result: MatchResult, language: str = "en"
) -> CoverLetter:
    jd = match_result.jd
    projects = match_result.matches[:3]
    proj_lines = "\n".join(
        f"- {m.project.name}: stack {m.project.stack}, "
        f"matched skills {m.matched_skills}"
        for m in projects
    )
    context = f"""Target role: {jd.role} at {jd.company}
Must-have skills: {[s.name for s in jd.must_skills]}
Plus skills: {[s.name for s in jd.plus_skills]}
Responsibilities: {jd.responsibilities}

Candidate's best-matching projects:
{proj_lines}"""

    lang_instr = (
        "\n\nWrite the entire letter in Chinese (Mandarin). Keep technology "
        "names in their original English casing."
        if language == "zh"
        else "\n\nWrite the entire letter in English."
    )
    return await call_llm_structured(
        system=SYSTEM_PROMPT + lang_instr,
        user_message=context,
        output_schema=CoverLetter,
    )
