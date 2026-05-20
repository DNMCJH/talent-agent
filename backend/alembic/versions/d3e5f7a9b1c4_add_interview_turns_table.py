"""add interview_turns table

Split unbounded JSON history out of interview_sessions.state into a
normalized table. Existing sessions keep their state JSON intact (the
service reads from both during transition).

Revision ID: d3e5f7a9b1c4
Revises: c2a4f8d1e9b3
Create Date: 2026-05-21 03:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d3e5f7a9b1c4"
down_revision: Union[str, None] = "c2a4f8d1e9b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "interview_turns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(64), sa.ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("idx", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("critique", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("interview_turns")
