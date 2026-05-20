"""reconcile users schema for email auth

Initial migration b14b17b06495 predates email/password registration. The
VPS database was manually patched at the time (ADD COLUMN password_hash,
ADD COLUMN email_verified, ALTER COLUMN github_id DROP NOT NULL, etc.)
without a corresponding alembic revision, leaving the prod schema drifted
from the alembic history.

This migration is idempotent: every statement is `IF NOT EXISTS` /
`DROP NOT NULL` so it is safe to run against the drifted VPS DB (where
the changes already exist) and against a fresh DB (where they don't).

Revision ID: c2a4f8d1e9b3
Revises: b14b17b06495
Create Date: 2026-05-21 02:00:00
"""
from typing import Sequence, Union

from alembic import op

revision: str = "c2a4f8d1e9b3"
down_revision: Union[str, None] = "b14b17b06495"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make GitHub identity optional (email-registered users have none).
    op.execute("ALTER TABLE users ALTER COLUMN github_id DROP NOT NULL")
    op.execute("ALTER TABLE users ALTER COLUMN github_login DROP NOT NULL")

    # New columns for password-based auth + email verification flow.
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)")
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN "
        "NOT NULL DEFAULT FALSE"
    )

    # email unique constraint (PG allows multiple NULLs, so OAuth-only users
    # without an email don't collide). DO block to make ADD CONSTRAINT idempotent.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'users_email_key'
            ) THEN
                ALTER TABLE users ADD CONSTRAINT users_email_key UNIQUE (email);
            END IF;
        END
        $$;
        """
    )

    # B-tree index for fast lookup by email (separate from the unique constraint
    # so existing manually-created indexes get picked up too).
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_users_email")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_email_key")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS email_verified")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS password_hash")
    op.execute("ALTER TABLE users ALTER COLUMN github_login SET NOT NULL")
    op.execute("ALTER TABLE users ALTER COLUMN github_id SET NOT NULL")
