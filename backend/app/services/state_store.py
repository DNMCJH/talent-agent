"""SQLite state store for sessions and weaknesses."""

from __future__ import annotations

from pathlib import Path

import aiosqlite

from app.core.config import settings
from app.schemas.agent_models import InterviewSession, WeaknessEntry

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    jd_hash TEXT NOT NULL,
    project_name TEXT NOT NULL,
    data JSON NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sessions_jd ON sessions(jd_hash);

CREATE TABLE IF NOT EXISTS weaknesses (
    topic TEXT PRIMARY KEY,
    count INTEGER DEFAULT 1,
    severity TEXT DEFAULT 'mild',
    last_seen TEXT,
    last_failure_summary TEXT DEFAULT ''
);
"""


async def _get_db() -> aiosqlite.Connection:
    db_path = Path(settings.state_db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(db_path))
    await db.executescript(_SCHEMA)
    return db


async def save_session(session: InterviewSession) -> None:
    db = await _get_db()
    try:
        await db.execute(
            """INSERT INTO sessions (session_id, jd_hash, project_name, data)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(session_id) DO UPDATE SET
                 data = excluded.data,
                 updated_at = datetime('now')""",
            (session.session_id, session.jd_hash, session.project_name, session.model_dump_json()),
        )
        await db.commit()
    finally:
        await db.close()


async def load_session(session_id: str) -> InterviewSession | None:
    db = await _get_db()
    try:
        cursor = await db.execute("SELECT data FROM sessions WHERE session_id = ?", (session_id,))
        row = await cursor.fetchone()
        if row:
            return InterviewSession.model_validate_json(row[0])
        return None
    finally:
        await db.close()


async def upsert_weakness(entry: WeaknessEntry) -> None:
    db = await _get_db()
    try:
        await db.execute(
            """INSERT INTO weaknesses (topic, count, severity, last_seen, last_failure_summary)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(topic) DO UPDATE SET
                 count = weaknesses.count + 1,
                 severity = excluded.severity,
                 last_seen = excluded.last_seen,
                 last_failure_summary = excluded.last_failure_summary""",
            (entry.topic, entry.count, entry.severity, entry.last_seen, entry.last_failure_summary),
        )
        await db.commit()
    finally:
        await db.close()


async def get_all_weaknesses() -> list[WeaknessEntry]:
    db = await _get_db()
    try:
        cursor = await db.execute("SELECT topic, count, severity, last_seen, last_failure_summary FROM weaknesses ORDER BY count DESC")
        rows = await cursor.fetchall()
        return [
            WeaknessEntry(topic=r[0], count=r[1], severity=r[2], last_seen=r[3] or "", last_failure_summary=r[4] or "")
            for r in rows
        ]
    finally:
        await db.close()
