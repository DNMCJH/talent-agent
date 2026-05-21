"""Interview session service: Postgres-backed, multi-tenant."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import _get_sessionmaker
from app.services.jd_parser import parse_jd
from app.services.interview_prompts import (
    COMPREHENSIVE_SYSTEM,
    CRITIQUE_SYSTEM,
    INTERVIEWER_SYSTEM,
    TARGETED_MULTI_SYSTEM,
)
from app.core.llm import call_llm, call_llm_chat, stream_llm, stream_llm_chat
from app.models.interview import InterviewSession as InterviewSessionORM
from app.models.interview import InterviewTurn, Weakness
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
    resume_context: str = "",
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

    rc_block = ""
    if resume_context:
        rc_block = f"\nCandidate background (from resume):\n{resume_context}\n"

    if is_comprehensive:
        system = COMPREHENSIVE_SYSTEM.format(
            company=company,
            role=role,
            projects_summary=summary,
            must_skills=must_skills or "none specified",
            weaknesses=weakness_text,
            focus="overall technical background (first question)",
            resume_context=rc_block,
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
            resume_context=rc_block,
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
            resume_context=rc_block,
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
        "resume_context": resume_context,
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
    await _save_turn(session, state.session_id, 0, "interviewer", first_question)
    await session.commit()

    return {
        "session_id": state.session_id,
        "interviewer_message": first_question,
        "turn_count": state.turn_count,
    }


def _state_dump(
    state: InterviewState, *, parsed: ParsedJD | None = None, extra: dict[str, Any] | None = None
) -> dict[str, Any]:
    # History is persisted in the interview_turns table; the JSON column keeps
    # only metadata so it cannot grow unbounded.
    payload = state.model_dump(exclude={"history"})
    if parsed is not None:
        payload["_parsed_jd"] = parsed.model_dump()
    if extra:
        payload["_extra"] = extra
    return payload


async def _load_state(
    row: InterviewSessionORM, session: AsyncSession
) -> tuple[InterviewState, ParsedJD | None, dict[str, Any]]:
    raw = dict(row.state)
    parsed_data = raw.pop("_parsed_jd", None)
    extra = raw.pop("_extra", {})
    # Legacy rows may still carry `history` inline — model_validate accepts it as
    # a fallback; turns from interview_turns take precedence when present.
    state = InterviewState.model_validate(raw)
    turns = await session.execute(
        select(InterviewTurn)
        .where(InterviewTurn.session_id == row.id)
        .order_by(InterviewTurn.idx)
    )
    turn_rows = turns.scalars().all()
    if turn_rows:
        state.history = [ChatTurn(role=t.role, content=t.content) for t in turn_rows]
    parsed = ParsedJD.model_validate(parsed_data) if parsed_data else None
    return state, parsed, extra


async def _save_turn(
    session: AsyncSession,
    session_id: str,
    idx: int,
    role: str,
    content: str,
    critique: dict[str, Any] | None = None,
) -> None:
    session.add(InterviewTurn(
        session_id=session_id,
        idx=idx,
        role=role,
        content=content,
        critique=critique,
    ))


async def take_turn(
    user_id: int,
    session_id: str,
    candidate_message: str,
    session: AsyncSession,
) -> dict[str, Any]:
    row = await session.get(InterviewSessionORM, session_id)
    if row is None or row.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "interview session not found")

    state, parsed, extra = await _load_state(row, session)
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
        max_tokens=500,
    )
    try:
        critique = json.loads(critique_raw)
    except json.JSONDecodeError:
        critique = {"score": 5, "weakness_topics": [], "severity": None, "next_focus": None, "feedback": {"summary": "", "suggestions": [], "corrections": []}}

    for topic in critique.get("weakness_topics") or []:
        await _bump_weakness(
            user_id, topic,
            severity=critique.get("severity", "轻微"),
            summary=candidate_message,
            session=session,
        )

    state.current_focus = critique.get("next_focus")

    company = parsed.company if parsed else "a tech company"
    role = parsed.role if parsed else "software engineer"
    must_skills = [s.name for s in parsed.must_skills] if parsed else []
    weakness_text = await _user_weaknesses_text(user_id, session)
    summary = _projects_summary(docs)

    rc_block = ""
    rc = extra.get("resume_context", "")
    if rc:
        rc_block = f"\nCandidate background (from resume):\n{rc}\n"

    if is_comprehensive:
        system = COMPREHENSIVE_SYSTEM.format(
            company=company,
            role=role,
            projects_summary=summary,
            must_skills=must_skills or "none specified",
            weaknesses=weakness_text,
            focus=state.current_focus or "continue probing",
            resume_context=rc_block,
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
            resume_context=rc_block,
        )
    else:
        system = TARGETED_MULTI_SYSTEM.format(
            company=company,
            role=role,
            projects_summary=summary,
            must_skills=must_skills,
            weaknesses=weakness_text,
            focus=state.current_focus or "continue probing",
            resume_context=rc_block,
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

    turn_base = len(state.history) - 2
    await _save_turn(session, session_id, turn_base, "candidate", candidate_message, critique)
    await _save_turn(session, session_id, turn_base + 1, "interviewer", next_question)

    row.state = _state_dump(state, parsed=parsed, extra=extra)
    await session.commit()

    return {
        "session_id": state.session_id,
        "interviewer_message": next_question,
        "turn_count": state.turn_count,
        "critique": critique,
    }


# ---------- streaming variants ----------
#
# Both stream functions yield dicts that the API layer formats as SSE events.
# Event shapes:
#   {"type": "delta", "text": "<chunk>"}      — incremental LLM output
#   {"type": "done",  ...}                    — final event with metadata
#   {"type": "error", "message": "..."}       — terminal error
#
# Critique runs in parallel with next-question streaming so the user does not wait
# for it. Final state commit happens after both finish.


def _build_interviewer_prompt(
    *,
    docs: list[ProjectDoc],
    is_comprehensive: bool,
    parsed: ParsedJD | None,
    weakness_text: str,
    focus: str,
    language: str,
    resume_context: str = "",
) -> str:
    company = parsed.company if parsed else "a tech company"
    role = parsed.role if parsed else "software engineer"
    must_skills = [s.name for s in parsed.must_skills] if parsed else []
    summary = _projects_summary(docs)

    rc_block = ""
    if resume_context:
        rc_block = f"\nCandidate background (from resume):\n{resume_context}\n"

    if is_comprehensive:
        system = COMPREHENSIVE_SYSTEM.format(
            company=company,
            role=role,
            projects_summary=summary,
            must_skills=must_skills or "none specified",
            weaknesses=weakness_text,
            focus=focus,
            resume_context=rc_block,
        )
    elif len(docs) == 1:
        system = INTERVIEWER_SYSTEM.format(
            company=company,
            role=role,
            project_name=docs[0].name,
            stack=docs[0].stack,
            must_skills=must_skills,
            weaknesses=weakness_text,
            focus=focus,
            resume_context=rc_block,
        )
    else:
        system = TARGETED_MULTI_SYSTEM.format(
            company=company,
            role=role,
            projects_summary=summary,
            must_skills=must_skills,
            weaknesses=weakness_text,
            focus=focus,
            resume_context=rc_block,
        )

    lang_instruction = (
        "\n\nIMPORTANT: Conduct this entire interview in Chinese (Mandarin). All your questions and responses must be in Chinese."
        if language == "zh"
        else "\n\nIMPORTANT: Conduct this entire interview in English. All your questions and responses must be in English."
    )
    return system + lang_instruction


async def start_interview_stream(
    user_id: int,
    project_ids: list[int],
    interview_type: str,
    mode: str,
    raw_jd: str,
    language: str,
    resume_context: str = "",
) -> AsyncIterator[dict[str, Any]]:
    """Streaming version of start_interview. Yields delta + final done event.

    Opens its own DB session: the request-scoped session injected by FastAPI is
    already closed by the time a StreamingResponse generator runs.
    """
    async with _get_sessionmaker()() as session:
        async for event in _start_interview_stream_impl(
            user_id, project_ids, interview_type, mode, raw_jd, language, session, resume_context
        ):
            yield event


async def _start_interview_stream_impl(
    user_id: int,
    project_ids: list[int],
    interview_type: str,
    mode: str,
    raw_jd: str,
    language: str,
    session: AsyncSession,
    resume_context: str = "",
) -> AsyncIterator[dict[str, Any]]:
    is_comprehensive = interview_type == "comprehensive"

    if is_comprehensive:
        docs = await _load_all_projects(user_id, session)
    else:
        if not project_ids:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "select at least one project")
        docs = await _load_projects(user_id, project_ids, session)

    parsed = None
    if raw_jd.strip():
        parsed = await parse_jd(raw_jd)

    weakness_text = await _user_weaknesses_text(user_id, session)
    system = _build_interviewer_prompt(
        docs=docs,
        is_comprehensive=is_comprehensive,
        parsed=parsed,
        weakness_text=weakness_text,
        focus=(
            "overall technical background (first question)"
            if is_comprehensive
            else "project overview (first question)"
        ),
        language=language,
        resume_context=resume_context,
    )
    if is_comprehensive:
        start_msg = "Start the comprehensive interview. Ask the candidate to introduce their technical background and project portfolio."
    elif len(docs) == 1:
        start_msg = "Start the interview. Ask your first question about the candidate's project."
    else:
        start_msg = "Start the interview. Ask the candidate to briefly introduce the projects, then drill into technical details."

    accumulated: list[str] = []
    async for chunk in stream_llm(system=system, user_message=start_msg, max_tokens=300):
        accumulated.append(chunk)
        yield {"type": "delta", "text": chunk}

    first_question = "".join(accumulated)
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
        "resume_context": resume_context,
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
    await _save_turn(session, state.session_id, 0, "interviewer", first_question)
    await session.commit()

    yield {
        "type": "done",
        "session_id": state.session_id,
        "turn_count": state.turn_count,
    }


async def _run_critique(
    user_id: int,
    last_question: str,
    candidate_message: str,
) -> dict[str, Any]:
    """Run critique LLM call and persist weakness updates in its own session."""
    critique_raw = await call_llm(
        system=CRITIQUE_SYSTEM,
        user_message=f"Question: {last_question}\nAnswer: {candidate_message}",
        max_tokens=500,
    )
    try:
        critique = json.loads(critique_raw)
    except json.JSONDecodeError:
        critique = {"score": 5, "weakness_topics": [], "severity": None, "next_focus": None, "feedback": {"summary": "", "suggestions": [], "corrections": []}}

    if critique.get("weakness_topics"):
        async with _get_sessionmaker()() as s:
            for topic in critique["weakness_topics"]:
                await _bump_weakness(
                    user_id, topic,
                    severity=critique.get("severity", "轻微"),
                    summary=candidate_message,
                    session=s,
                )
            await s.commit()
    return critique


async def take_turn_stream(
    user_id: int,
    session_id: str,
    candidate_message: str,
) -> AsyncIterator[dict[str, Any]]:
    """Streaming version of take_turn. Opens its own DB session — see
    start_interview_stream for why the injected session cannot be used here."""
    async with _get_sessionmaker()() as session:
        async for event in _take_turn_stream_impl(
            user_id, session_id, candidate_message, session
        ):
            yield event


async def _take_turn_stream_impl(
    user_id: int,
    session_id: str,
    candidate_message: str,
    session: AsyncSession,
) -> AsyncIterator[dict[str, Any]]:
    """Critique runs concurrently with next-question streaming so the user sees the
    next question immediately; critique surfaces as the final event."""
    row = await session.get(InterviewSessionORM, session_id)
    if row is None or row.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "interview session not found")

    state, parsed, extra = await _load_state(row, session)
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

    # Fire critique in the background — it does not block next-question generation.
    # Uses its own session internally to avoid concurrent writes on one connection.
    critique_task = asyncio.create_task(
        _run_critique(user_id, last_question, candidate_message)
    )

    # Use focus from PREVIOUS turn (already persisted in state.current_focus).
    # New focus from this turn's critique is applied to NEXT turn's prompt.
    weakness_text = await _user_weaknesses_text(user_id, session)
    lang = extra.get("language", "en")
    system = _build_interviewer_prompt(
        docs=docs,
        is_comprehensive=is_comprehensive,
        parsed=parsed,
        weakness_text=weakness_text,
        focus=state.current_focus or "continue probing",
        language=lang,
        resume_context=extra.get("resume_context", ""),
    )

    messages = [
        {"role": "assistant" if t.role == "interviewer" else "user", "content": t.content}
        for t in state.history
    ]

    accumulated: list[str] = []
    async for chunk in stream_llm_chat(system=system, messages=messages, max_tokens=300):
        accumulated.append(chunk)
        yield {"type": "delta", "text": chunk}

    next_question = "".join(accumulated)
    state.history.append(ChatTurn(role="interviewer", content=next_question))
    state.turn_count += 1

    # Now wait for the critique to finish so we can update state.current_focus
    # and surface it to the client.
    critique = await critique_task
    state.current_focus = critique.get("next_focus")

    turn_base = len(state.history) - 2
    await _save_turn(session, session_id, turn_base, "candidate", candidate_message, critique)
    await _save_turn(session, session_id, turn_base + 1, "interviewer", next_question)

    row.state = _state_dump(state, parsed=parsed, extra=extra)
    await session.commit()

    yield {
        "type": "done",
        "session_id": state.session_id,
        "turn_count": state.turn_count,
        "critique": critique,
    }
