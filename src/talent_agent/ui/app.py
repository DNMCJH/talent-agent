"""Streamlit UI for talent-agent."""

from __future__ import annotations

import os

os.environ.setdefault("TQDM_DISABLE", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import asyncio
from pathlib import Path

import streamlit as st

from talent_agent.agents.interviewer import init_interview, interview_turn
from talent_agent.config import settings
from talent_agent.graph.pipeline import run_pipeline


def _run_async(coro):
    """Run async code from Streamlit's sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@st.cache_resource(show_spinner="Loading Qdrant index...")
def _qdrant_client():
    from qdrant_client import QdrantClient
    if settings.qdrant_url:
        return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
    Path(settings.qdrant_local_path).mkdir(parents=True, exist_ok=True)
    return QdrantClient(path=settings.qdrant_local_path)


@st.cache_resource(show_spinner="Loading embedding model (bge-small-zh, ~95MB)...")
def _embedder():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(settings.embed_model, device=settings.embed_device)


def main():
    st.set_page_config(page_title="talent-agent", page_icon="🎯", layout="wide")
    st.title("talent-agent")
    st.caption("Agentic JD-to-project matching · DeepSeek + BGE + Qdrant")

    _render_sidebar()

    tab_match, tab_interview = st.tabs(["Match & Plan", "Interview Drill"])
    with tab_match:
        _render_match_tab()
    with tab_interview:
        _render_interview_tab()


def _render_sidebar():
    with st.sidebar:
        st.subheader("Status")
        try:
            qc = _qdrant_client()
            count = qc.count(collection_name=settings.qdrant_collection_projects, exact=False).count
            st.success(f"Index: {count} projects")
        except Exception as e:
            st.error(f"Index error: {e}")

        st.caption(f"LLM: `{settings.llm_model}`")
        st.caption(f"Embed: `{settings.embed_model}`")

        if st.session_state.get("interview"):
            sess = st.session_state["interview"]
            st.subheader("Mock interview")
            st.caption(f"Turn: {sess.turn_count}")
            if sess.weaknesses:
                st.markdown("**Weak areas**")
                for topic, w in sess.weaknesses.items():
                    color = {"mild": "🟡", "moderate": "🟠", "severe": "🔴"}.get(w.severity, "⚪")
                    st.markdown(f"{color} **{topic}** ×{w.count}")
            if st.button("Reset interview"):
                for k in ("interview", "parsed_jd", "project"):
                    st.session_state.pop(k, None)
                st.rerun()


def _render_match_tab():
    jd_text = st.text_area("Paste JD here", height=260, placeholder="Paste a job description...")

    col1, col2 = st.columns([2, 1])
    with col1:
        intent_choice = st.selectbox(
            "Pipeline depth",
            [
                ("full_loop", "Full loop (match → improve → resume → interview)"),
                ("match_only", "Match only"),
                ("improve_only", "Match + Improvement plan"),
                ("resume_only", "Match + Resume bullets"),
            ],
            format_func=lambda x: x[1],
        )
    with col2:
        st.markdown("")
        st.markdown("")
        run_clicked = st.button("Run pipeline", type="primary", disabled=not jd_text.strip(), use_container_width=True)

    if run_clicked:
        with st.spinner("Running pipeline..."):
            session = _run_async(
                run_pipeline(
                    jd_text,
                    intent=intent_choice[0],
                    qdrant=_qdrant_client(),
                    embedder=_embedder(),
                )
            )
        st.session_state["last_session"] = session

    session = st.session_state.get("last_session")
    if not session:
        return

    if session.parsed:
        st.subheader(f"📋 {session.parsed.role} @ {session.parsed.company}")
        col_must, col_plus = st.columns(2)
        with col_must:
            st.markdown("**Must-have skills**")
            for s in session.parsed.must_skills:
                st.markdown(f"- {s.name} _({s.level})_")
        with col_plus:
            st.markdown("**Plus skills**")
            for s in session.parsed.plus_skills:
                st.markdown(f"- {s.name} _({s.level})_")

    if session.match:
        st.subheader("🎯 Best matches")
        for i, m in enumerate(session.match.matches[:3]):
            label = (
                f"#{i+1} {m.project.name} — "
                f"weighted {m.weighted_score:.0%} "
                f"(must {m.coverage:.0%} / plus {m.plus_coverage:.0%})"
            )
            with st.expander(label, expanded=(i == 0)):
                st.markdown(f"**Matched must:** {', '.join(m.matched_skills) or '—'}")
                st.markdown(f"**Matched plus:** {', '.join(m.matched_plus_skills) or '—'}")
                st.markdown(f"**Missing must:** {', '.join(m.missing_skills) or '—'}")
                if m.match_reason:
                    st.markdown(f"**Why:** {m.match_reason}")
                st.markdown(f"Stack: `{' · '.join(m.project.stack)}`")

    if session.plan:
        st.subheader("🔧 Improvement tasks")
        for t in session.plan.tasks:
            with st.expander(f"{t.title} · {t.effort_days}d"):
                st.markdown(f"**Addresses:** {', '.join(t.addresses_gaps)}")
                st.markdown(f"**Deliverables:** {', '.join(t.deliverables)}")
                st.markdown(f"**Resume impact:** {t.resume_impact}")
                if t.implementation_hints:
                    st.markdown(f"**Hints:** {t.implementation_hints}")

    if session.resume:
        st.subheader("📝 Resume bullets")
        st.code(session.resume.stack_line, language="text")
        for bullet in session.resume.star_bullets:
            st.markdown(f"- {bullet}")
        if session.resume.metrics_placeholders:
            st.info(f"Fill in metrics: {', '.join(session.resume.metrics_placeholders)}")

    if session.interview:
        st.session_state["interview"] = session.interview
        st.session_state["parsed_jd"] = session.parsed
        st.session_state["project"] = session.match.overall_best.project
        st.info("Interview ready — switch to **Interview Drill** tab.")
    elif session.match and "interview" not in st.session_state:
        if st.button("Start interview with top match"):
            with st.spinner("Initializing interview..."):
                interview = _run_async(
                    init_interview(session.parsed, session.match.overall_best.project)
                )
            st.session_state["interview"] = interview
            st.session_state["parsed_jd"] = session.parsed
            st.session_state["project"] = session.match.overall_best.project
            st.rerun()


def _render_interview_tab():
    if "interview" not in st.session_state:
        st.info("Run a match (with `full_loop` or click *Start interview*) to begin.")
        return

    session = st.session_state["interview"]
    jd = st.session_state["parsed_jd"]
    project = st.session_state["project"]

    st.subheader(f"Mock interview — {jd.role} @ {jd.company}")
    st.caption(f"Project: {project.name} · Turn {session.turn_count}")

    for turn in session.history:
        role = "assistant" if turn.role == "interviewer" else "user"
        st.chat_message(role).write(turn.content)

    answer = st.chat_input("Your answer...")
    if answer:
        with st.spinner("Interviewer thinking..."):
            updated, _ = _run_async(interview_turn(session, answer, jd, project))
        st.session_state["interview"] = updated
        st.rerun()


if __name__ == "__main__":
    main()
