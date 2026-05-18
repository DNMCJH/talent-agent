from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # UUID4
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    mode: Mapped[str] = mapped_column(String(20))  # 'tech' | 'stress' | 'behavior'
    jd_hash: Mapped[str] = mapped_column(String(64), index=True)
    project_name: Mapped[str] = mapped_column(String(200))

    # Full InterviewSession schema (schemas.agent_models.InterviewSession.model_dump())
    state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Weakness(Base):
    """Per-user weakness tracking. Aggregated across all interview sessions."""
    __tablename__ = "weaknesses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic: Mapped[str] = mapped_column(String(200), index=True)
    count: Mapped[int] = mapped_column(default=1)
    severity: Mapped[str] = mapped_column(String(20), default="mild")
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_failure_summary: Mapped[str] = mapped_column(default="")
