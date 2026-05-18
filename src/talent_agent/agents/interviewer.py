"""Interviewer agent: adaptive multi-turn mock interview with weakness tracking."""

from __future__ import annotations

import uuid
from datetime import datetime

from talent_agent.llm import call_llm, call_llm_chat
from talent_agent.models import (
    ChatTurn,
    InterviewSession,
    ParsedJD,
    ProjectDoc,
    WeaknessEntry,
)
from talent_agent.store import get_all_weaknesses, save_session, upsert_weakness

INTERVIEWER_SYSTEM = """You are a senior tech interviewer at {company} hiring for {role}.

You are interviewing a candidate about their project: {project_name}.
Tech stack: {stack}

Interview style:
- Ask one focused question at a time
- Start with project overview, then drill into technical decisions
- If the candidate's answer is weak, probe deeper on that topic (don't move on)
- Cover: architecture decisions, trade-offs, failure modes, scaling, testing strategy
- Prioritize topics from the JD's required skills: {must_skills}
- Be professional but direct. Don't be overly encouraging for weak answers.

Known weak areas from previous sessions (probe these harder):
{weaknesses}

Current focus area: {focus}
"""

CRITIQUE_SYSTEM = """Evaluate the candidate's interview answer. Return a JSON object:
{
  "score": 0-5 (0=no answer, 1=wrong, 2=vague, 3=acceptable, 4=good, 5=excellent),
  "weakness_topics": ["topic1", ...] (skills/concepts the candidate struggled with, empty if score >= 4),
  "severity": "mild" | "moderate" | "severe" (only if weakness_topics non-empty),
  "next_focus": "topic to probe next based on this answer"
}

Be strict. A score of 3 means "would pass but not impress". Only give 5 for answers that show deep understanding with concrete examples."""


async def init_interview(jd: ParsedJD, project: ProjectDoc) -> InterviewSession:
    session = InterviewSession(
        session_id=str(uuid.uuid4()),
        jd_hash=jd.jd_hash,
        project_name=project.name,
    )

    existing_weaknesses = await get_all_weaknesses()
    weakness_text = ", ".join(f"{w.topic}({w.severity})" for w in existing_weaknesses[:10]) or "none yet"

    system = INTERVIEWER_SYSTEM.format(
        company=jd.company,
        role=jd.role,
        project_name=project.name,
        stack=project.stack,
        must_skills=[s.name for s in jd.must_skills],
        weaknesses=weakness_text,
        focus="project overview (first question)",
    )

    first_question = await call_llm(
        system=system,
        user_message="Start the interview. Ask your first question about the candidate's project.",
        max_tokens=300,
    )

    session.history.append(ChatTurn(role="interviewer", content=first_question))
    session.turn_count = 1
    await save_session(session)
    return session


async def interview_turn(
    session: InterviewSession, candidate_answer: str, jd: ParsedJD, project: ProjectDoc
) -> tuple[InterviewSession, str]:
    session.history.append(ChatTurn(role="candidate", content=candidate_answer))

    import json
    critique_input = f"Question: {session.history[-2].content}\nAnswer: {candidate_answer}"
    critique_raw = await call_llm(system=CRITIQUE_SYSTEM, user_message=critique_input, max_tokens=200)

    try:
        critique = json.loads(critique_raw)
    except json.JSONDecodeError:
        critique = {"score": 3, "weakness_topics": [], "severity": "mild", "next_focus": None}

    for topic in critique.get("weakness_topics", []):
        entry = WeaknessEntry(
            topic=topic,
            severity=critique.get("severity", "mild"),
            last_seen=datetime.now().isoformat(),
            last_failure_summary=candidate_answer[:200],
        )
        await upsert_weakness(entry)
        session.weaknesses[topic] = entry

    session.current_focus = critique.get("next_focus")

    existing_weaknesses = await get_all_weaknesses()
    weakness_text = ", ".join(f"{w.topic}({w.severity})" for w in existing_weaknesses[:10]) or "none yet"

    system = INTERVIEWER_SYSTEM.format(
        company=jd.company,
        role=jd.role,
        project_name=project.name,
        stack=project.stack,
        must_skills=[s.name for s in jd.must_skills],
        weaknesses=weakness_text,
        focus=session.current_focus or "continue probing",
    )

    messages = [
        {"role": "assistant" if t.role == "interviewer" else "user", "content": t.content}
        for t in session.history
    ]

    next_question = await call_llm_chat(system=system, messages=messages, max_tokens=300)

    session.history.append(ChatTurn(role="interviewer", content=next_question))
    session.turn_count += 1
    await save_session(session)

    return session, next_question
