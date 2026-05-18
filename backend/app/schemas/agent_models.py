"""Pydantic models shared across all agents."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Skill(BaseModel):
    name: str
    level: Literal["basic", "intermediate", "advanced"]
    aliases: list[str] = []


class ImplicitSignals(BaseModel):
    team_style: str = ""
    production_vs_research: Literal["production", "research", "mixed"] = "production"
    seniority_expectation: Literal["intern", "junior", "mid", "senior"] = "intern"


class ParsedJD(BaseModel):
    raw: str
    language: Literal["en", "zh"]
    company: str
    role: str
    location: str | None = None
    work_mode: Literal["onsite", "hybrid", "remote"] | None = None
    must_skills: list[Skill]
    plus_skills: list[Skill]
    responsibilities: list[str]
    implicit_signals: ImplicitSignals
    keywords_for_search: list[str]
    jd_hash: str


class ProjectDoc(BaseModel):
    name: str
    path: str
    readme: str
    stack: list[str]
    languages: dict[str, float] = {}
    topics: list[str] = []
    last_commit_date: str = ""
    commit_count: int = 0
    has_dockerfile: bool = False
    has_tests: bool = False
    deployment_signal: bool = False
    complexity_loc: int = 0
    sample_files: list[str] = []


class Match(BaseModel):
    project: ProjectDoc
    coverage: float
    plus_coverage: float = 0.0
    weighted_score: float = 0.0
    matched_skills: list[str]
    missing_skills: list[str]
    matched_plus_skills: list[str] = []
    bonus_skills: list[str] = []
    match_reason: str = ""


class MatchResult(BaseModel):
    jd: ParsedJD
    matches: list[Match]
    overall_best: Match


class Task(BaseModel):
    title: str
    addresses_gaps: list[str]
    effort_days: int
    deliverables: list[str]
    implementation_hints: str = ""
    resume_impact: str = ""


class ImprovementPlan(BaseModel):
    project_name: str
    tasks: list[Task]


class ResumeBundle(BaseModel):
    project_title: str
    stack_line: str
    star_bullets: list[str]
    metrics_placeholders: list[str] = []
    tailored_for_role: str = ""


class WeaknessEntry(BaseModel):
    topic: str
    count: int = 1
    severity: Literal["mild", "moderate", "severe"] = "mild"
    last_seen: str = ""
    last_failure_summary: str = ""


class ChatTurn(BaseModel):
    role: Literal["interviewer", "candidate"]
    content: str


class InterviewSession(BaseModel):
    session_id: str
    jd_hash: str
    project_name: str
    history: list[ChatTurn] = []
    weaknesses: dict[str, WeaknessEntry] = {}
    current_focus: str | None = None
    turn_count: int = 0
