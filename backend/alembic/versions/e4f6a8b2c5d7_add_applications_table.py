"""add applications table

Job-application tracker: each row is one application the user is tracking
through its lifecycle (saved → applied → interviewing → offer/rejected).

Revision ID: e4f6a8b2c5d7
Revises: d3e5f7a9b1c4
Create Date: 2026-05-23 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e4f6a8b2c5d7"
down_revision: Union[str, None] = "d3e5f7a9b1c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("company", sa.String(200), nullable=False),
        sa.Column("role", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="saved"),
        sa.Column("link", sa.String(500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("applications")
