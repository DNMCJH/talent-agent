"""Interview session service: Postgres-backed, multi-tenant.

Borrows the prompts from app.agents.interviewer but takes care of persistence
via SQLAlchemy ORM rather than the SQLite state_store (which is Streamlit-era).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.parser import parse_jd
from app.services.interview_prompts import CRITIQUE_SYSTEM, INTERVIEWER_SYSTEM
from app.core.llm import call_llm, call_llm_chat
from app.models.interview import InterviewSession as InterviewSessionORM
from app.models.interview import Weakness
from app.models.project import Project
from app.schemas.agent_models import (
    ChatTurn,
    ParsedJD,
    ProjectDoc,
)
from app.schemas.agent_models import InterviewSession as InterviewState


async def _load_project(
    user_id: int, project_id: int, session: AsyncSession
) -> ProjectDoc:
    proj = await session.get(Project, project_id)
    if proj is None or proj.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    if not proj.doc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "project has no indexed doc yet — re-import it",
        )
    return ProjectDoc.model_validate(proj.doc)


async def _user_weaknesses_text(user_id: int, session: AsyncSession, limit: int = 10) -> str:
    rows = await session.execute(
        select(Weakness)
        .where(Weakness.user_id == user_id)
        .order_by(Weakness.count.desc())
        .limit(limit)
    )
    items = [f"{w.topic}({w.severity})" for w in rows.scalars()]
    return ", ".join(items) or "none yet"


async def _bump_weakness(
    user_id: int, topic: str, severity: str, summary: str, session: AsyncSession
) -> None:
    existing = await session.execute(
        select(Weakness).where(Weakness.user_id == user_id, Weakness.topic == topic)
    )
    row = existing.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if row is None:
        session.add(Weakness(
            user_id=user_id, topic=topic, count=1, severity=severity,
            last_seen=now, last_failure_summary=summary[:200],
        ))
    else:
        row.count += 1
        row.severity = severity
        row.last_seen = now
        row.last_failure_summary = summary[:200]


async def start_interview(
    user_id: int,
    project_id: int,
    mode: str,
    raw_jd: str,
    session: AsyncSession,
) -> dict[str, Any]:
    project = await _load_project(user_id, project_id, session)
    parsed = await parse_jd(raw_jd)

    weakness_text = await _user_weaknesses_text(user_id, session)

    system = INTERVIEWER_SYSTEM.format(
        company=parsed.company,
        role=parsed.role,
        project_name=project.name,
        stack=project.stack,
        must_skills=[s.name for s in parsed.must_skills],
        weaknesses=weakness_text,
        focus="project overview (first question)",
    )
    first_question = await call_llm(
        system=system,
        user_message="Start the interview. Ask your first question about the candidate's project.",
        max_tokens=300,
    )

    state = InterviewState(
        session_id=str(uuid.uuid4()),
        jd_hash=parsed.jd_hash,
        project_name=project.name,
        history=[ChatTurn(role="interviewer", content=first_question)],
        turn_count=1,
    )

    orm_row = InterviewSessionORM(
        id=state.session_id,
        user_id=user_id,
        mode=mode,
        jd_hash=parsed.jd_hash,
        project_name=project.name,
        state=_state_dump(state, parsed=parsed),
    )
    session.add(orm_row)
    await session.commit()

    return {
        "session_id": state.session_id,
        "interviewer_message": first_question,
        "turn_count": state.turn_count,
    }


def _state_dump(state: InterviewState, *, parsed: ParsedJD | None = None) -> dict[str, Any]:
    """Combine the InterviewState pydantic dump with the parsed JD so /turn can rehydrate
    without re-running parse_jd on every turn."""
    payload = state.model_dump()
    if parsed is not None:
        payload["_parsed_jd"] = parsed.model_dump()
    return payload


def _load_state(row: InterviewSessionORM) -> tuple[InterviewState, ParsedJD | None]:
    raw = dict(row.state)
    parsed_data = raw.pop("_parsed_jd", None)
    state = InterviewState.model_validate(raw)
    parsed = ParsedJD.model_validate(parsed_data) if parsed_data else None
    return state, parsed


async def take_turn(
    user_id: int,
    session_id: str,
    candidate_message: str,
    session: AsyncSession,
) -> dict[str, Any]:
    row = await session.get(InterviewSessionORM, session_id)
    if row is None or row.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "interview session not found")

    state, parsed = _load_state(row)
    if parsed is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "session is missing parsed JD — start a new interview",
        )

    # Find the project doc again (name match is stable enough; doc is cached in ORM row otherwise)
    proj_rows = await session.execute(
        select(Project).where(
            Project.user_id == user_id, Project.name == state.project_name
        ).limit(1)
    )
    proj = proj_rows.scalar_one_or_none()
    if proj is None or not proj.doc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "the project this interview was about has been deleted",
        )
    project = ProjectDoc.model_validate(proj.doc)

    state.history.append(ChatTurn(role="candidate", content=candidate_message))

    last_question = state.history[-2].content if len(state.history) >= 2 else ""
    critique_raw = await call_llm(
        system=CRITIQUE_SYSTEM,
        user_message=f"Question: {last_question}\nAnswer: {candidate_message}",
        max_tokens=200,
    )
    try:
        critique = json.loads(critique_raw)
    except json.JSONDecodeError:
        critique = {"score": 3, "weakness_topics": [], "severity": "mild", "next_focus": None}

    for topic in critique.get("weakness_topics") or []:
        await _bump_weakness(
            user_id, topic,
            severity=critique.get("severity", "mild"),
            summary=candidate_message,
            session=session,
        )

    state.current_focus = critique.get("next_focus")

    weakness_text = await _user_weaknesses_text(user_id, session)
    system = INTERVIEWER_SYSTEM.format(
        company=parsed.company,
        role=parsed.role,
        project_name=project.name,
        stack=project.stack,
        must_skills=[s.name for s in parsed.must_skills],
        weaknesses=weakness_text,
        focus=state.current_focus or "continue probing",
    )
    messages = [
        {"role": "assistant" if t.role == "interviewer" else "user", "content": t.content}
        for t in state.history
    ]
    next_question = await call_llm_chat(system=system, messages=messages, max_tokens=300)

    state.history.append(ChatTurn(role="interviewer", content=next_question))
    state.turn_count += 1

    row.state = _state_dump(state, parsed=parsed)
    await session.commit()

    return {
        "session_id": state.session_id,
        "interviewer_message": next_question,
        "turn_count": state.turn_count,
        "critique": critique,
    }
