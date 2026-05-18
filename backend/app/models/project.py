from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Project(Base):
    """Project metadata. Vector embeddings live in Qdrant (payload.user_id filters tenancy)."""
    __tablename__ = "projects"
    __table_args__ = (Index("ix_projects_user_name", "user_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    name: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(20))  # 'github' | 'upload' | 'manual'
    github_url: Mapped[str | None] = mapped_column(String(500), default=None)
    analysis_depth: Mapped[str] = mapped_column(String(20), default="medium")  # 'medium' | 'heavy'

    # Cached ProjectDoc payload (schemas.agent_models.ProjectDoc.model_dump())
    doc: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # Qdrant point id (UUID string) for this project's embedding
    qdrant_point_id: Mapped[str | None] = mapped_column(String(64), default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
