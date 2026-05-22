"""Interview debrief: aggregate per-turn critiques into an end-of-session report."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import call_llm_structured
from app.models.interview import InterviewSession as InterviewSessionORM
from app.models.interview import InterviewTurn
from app.schemas.agent_models import InterviewDebrief

SYSTEM_PROMPT = """You are a senior interviewer writing a debrief report for a mock interview.

You are given the full interview transcript with per-answer critique scores and
feedback. Produce a structured debrief that:
1. overall_score (1-10) — holistic, weighing depth, clarity, and correctness
2. summary — 2-3 sentences on how the candidate did overall
3. strengths — 2-4 concrete things the candidate did well (cite specifics)
4. weaknesses — 2-4 concrete gaps, each actionable (not vague)
5. recommendations — 2-4 next steps to improve before a real interview
6. areas — score 2-4 named competency areas that actually came up (e.g. project
   depth, system design, communication, fundamentals); skip areas not covered

Be honest and specific. This is practice — useful criticism matters more than
encouragement. Ground every point in what the transcript actually shows.
"""


async def generate_debrief(
    user_id: int,
    session_id: str,
    session: AsyncSession,
    language: str = "en",
) -> InterviewDebrief:
    row = await session.get(InterviewSessionORM, session_id)
    if row is None or row.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "interview session not found")

    turns = await session.execute(
        select(InterviewTurn)
        .where(InterviewTurn.session_id == session_id)
        .order_by(InterviewTurn.idx)
    )
    turn_rows = list(turns.scalars())
    answered = [t for t in turn_rows if t.role == "candidate"]
    if not answered:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "no answers yet — finish at least one question first",
        )

    # Build a transcript with each answer's critique inline so the model can
    # ground the debrief in concrete per-turn evidence.
    blocks: list[str] = []
    last_q = ""
    for t in turn_rows:
        if t.role == "interviewer":
            last_q = t.content
            continue
        crit = t.critique or {}
        fb = crit.get("feedback") or {}
        blocks.append(
            f"Q: {last_q}\n"
            f"A: {t.content}\n"
            f"[score {crit.get('score', '?')}/10] {fb.get('summary', '')}"
        )

    context = (
        f"Interview for: {row.project_name} (mode: {row.mode})\n"
        f"{len(answered)} questions answered.\n\n"
        + "\n\n".join(blocks)
    )

    lang_instr = (
        "\n\nWrite the entire debrief in Chinese (Mandarin). Keep technology "
        "names in their original English casing."
        if language == "zh"
        else "\n\nWrite the entire debrief in English."
    )
    return await call_llm_structured(
        system=SYSTEM_PROMPT + lang_instr,
        user_message=context,
        output_schema=InterviewDebrief,
        provider="claude",
    )
