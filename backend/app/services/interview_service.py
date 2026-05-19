"""Interview session service: Postgres-backed, multi-tenant."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.jd_parser import parse_jd
from app.services.interview_prompts import (
    COMPREHENSIVE_SYSTEM,
    CRITIQUE_SYSTEM,
    INTERVIEWER_SYSTEM,
    TARGETED_MULTI_SYSTEM,
)
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


async def _load_projects(
    user_id: int, project_ids: list[int], session: AsyncSession
) -> list[ProjectDoc]:
    docs = []
    for pid in project_ids:
        proj = await session.get(Project, pid)
        if proj is None or proj.user_id != user_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"project {pid} not found")
        if not proj.doc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"project {pid} has no indexed doc yet — re-import it",
            )
        docs.append(ProjectDoc.model_validate(proj.doc))
    return docs


async def _load_all_projects(user_id: int, session: AsyncSession) -> list[ProjectDoc]:
    rows = await session.execute(
        select(Project).where(Project.user_id == user_id, Project.doc.isnot(None))
    )
    projects = rows.scalars().all()
    if not projects:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "no projects imported yet")
    return [ProjectDoc.model_validate(p.doc) for p in projects]


def _projects_summary(docs: list[ProjectDoc]) -> str:
    lines = []
    for i, d in enumerate(docs, 1):
        lines.append(f"{i}. {d.name} — stack: {d.stack}")
    return "\n".join(lines)


async def start_interview(
    user_id: int,
    project_ids: list[int],
    interview_type: str,
    mode: str,
    raw_jd: str,
    language: str,
    session: AsyncSession,
) -> dict[str, Any]:
    is_comprehensive = interview_type == "comprehensive"

    if is_comprehensive:
        docs = await _load_all_projects(user_id, session)
    else:
        if not project_ids:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "select at least one project")
        docs = await _load_projects(user_id, project_ids, session)

    parsed = None
    company = "a tech company"
    role = "software engineer"
    must_skills: list[str] = []
    if raw_jd.strip():
        parsed = await parse_jd(raw_jd)
        company = parsed.company
        role = parsed.role
        must_skills = [s.name for s in parsed.must_skills]

    weakness_text = await _user_weaknesses_text(user_id, session)
    summary = _projects_summary(docs)

    if is_comprehensive:
        system = COMPREHENSIVE_SYSTEM.format(
            company=company,
            role=role,
            projects_summary=summary,
            must_skills=must_skills or "none specified",
            weaknesses=weakness_text,
            focus="overall technical background (first question)",
        )
        start_msg = "Start the comprehensive interview. Ask the candidate to introduce their technical background and project portfolio."
    elif len(docs) == 1:
        system = INTERVIEWER_SYSTEM.format(
            company=company,
            role=role,
            project_name=docs[0].name,
            stack=docs[0].stack,
            must_skills=must_skills,
            weaknesses=weakness_text,
            focus="project overview (first question)",
        )
        start_msg = "Start the interview. Ask your first question about the candidate's project."
    else:
        system = TARGETED_MULTI_SYSTEM.format(
            company=company,
            role=role,
            projects_summary=summary,
            must_skills=must_skills,
            weaknesses=weakness_text,
            focus="project overview (first question)",
        )
        start_msg = "Start the interview. Ask the candidate to briefly introduce the projects, then drill into technical details."

    lang_instruction = (
        "\n\nIMPORTANT: Conduct this entire interview in Chinese (Mandarin). All your questions and responses must be in Chinese."
        if language == "zh"
        else "\n\nIMPORTANT: Conduct this entire interview in English. All your questions and responses must be in English."
    )
    system += lang_instruction

    first_question = await call_llm(system=system, user_message=start_msg, max_tokens=300)

    project_name = docs[0].name if len(docs) == 1 else f"[{len(docs)} projects]"
    state = InterviewState(
        session_id=str(uuid.uuid4()),
        jd_hash=parsed.jd_hash if parsed else "",
        project_name=project_name,
        history=[ChatTurn(role="interviewer", content=first_question)],
        turn_count=1,
    )

    extra_state = {
        "interview_type": interview_type,
        "project_ids": project_ids if not is_comprehensive else [],
        "language": language,
    }

    orm_row = InterviewSessionORM(
        id=state.session_id,
        user_id=user_id,
        mode=mode,
        jd_hash=parsed.jd_hash if parsed else "",
        project_name=project_name,
        state=_state_dump(state, parsed=parsed, extra=extra_state),
    )
    session.add(orm_row)
    await session.commit()

    return {
        "session_id": state.session_id,
        "interviewer_message": first_question,
        "turn_count": state.turn_count,
    }


def _state_dump(
    state: InterviewState, *, parsed: ParsedJD | None = None, extra: dict[str, Any] | None = None
) -> dict[str, Any]:
    payload = state.model_dump()
    if parsed is not None:
        payload["_parsed_jd"] = parsed.model_dump()
    if extra:
        payload["_extra"] = extra
    return payload


def _load_state(row: InterviewSessionORM) -> tuple[InterviewState, ParsedJD | None, dict[str, Any]]:
    raw = dict(row.state)
    parsed_data = raw.pop("_parsed_jd", None)
    extra = raw.pop("_extra", {})
    state = InterviewState.model_validate(raw)
    parsed = ParsedJD.model_validate(parsed_data) if parsed_data else None
    return state, parsed, extra


async def take_turn(
    user_id: int,
    session_id: str,
    candidate_message: str,
    session: AsyncSession,
) -> dict[str, Any]:
    row = await session.get(InterviewSessionORM, session_id)
    if row is None or row.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "interview session not found")

    state, parsed, extra = _load_state(row)
    interview_type = extra.get("interview_type", "targeted")
    stored_project_ids = extra.get("project_ids", [])

    is_comprehensive = interview_type == "comprehensive"

    if is_comprehensive:
        docs = await _load_all_projects(user_id, session)
    elif stored_project_ids:
        docs = await _load_projects(user_id, stored_project_ids, session)
    else:
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
        docs = [ProjectDoc.model_validate(proj.doc)]

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

    company = parsed.company if parsed else "a tech company"
    role = parsed.role if parsed else "software engineer"
    must_skills = [s.name for s in parsed.must_skills] if parsed else []
    weakness_text = await _user_weaknesses_text(user_id, session)
    summary = _projects_summary(docs)

    if is_comprehensive:
        system = COMPREHENSIVE_SYSTEM.format(
            company=company,
            role=role,
            projects_summary=summary,
            must_skills=must_skills or "none specified",
            weaknesses=weakness_text,
            focus=state.current_focus or "continue probing",
        )
    elif len(docs) == 1:
        system = INTERVIEWER_SYSTEM.format(
            company=company,
            role=role,
            project_name=docs[0].name,
            stack=docs[0].stack,
            must_skills=must_skills,
            weaknesses=weakness_text,
            focus=state.current_focus or "continue probing",
        )
    else:
        system = TARGETED_MULTI_SYSTEM.format(
            company=company,
            role=role,
            projects_summary=summary,
            must_skills=must_skills,
            weaknesses=weakness_text,
            focus=state.current_focus or "continue probing",
        )

    lang = extra.get("language", "en")
    lang_instruction = (
        "\n\nIMPORTANT: Conduct this entire interview in Chinese (Mandarin). All your questions and responses must be in Chinese."
        if lang == "zh"
        else "\n\nIMPORTANT: Conduct this entire interview in English. All your questions and responses must be in English."
    )
    system += lang_instruction

    messages = [
        {"role": "assistant" if t.role == "interviewer" else "user", "content": t.content}
        for t in state.history
    ]
    next_question = await call_llm_chat(system=system, messages=messages, max_tokens=300)

    state.history.append(ChatTurn(role="interviewer", content=next_question))
    state.turn_count += 1

    row.state = _state_dump(state, parsed=parsed, extra=extra)
    await session.commit()

    return {
        "session_id": state.session_id,
        "interviewer_message": next_question,
        "turn_count": state.turn_count,
        "critique": critique,
    }
