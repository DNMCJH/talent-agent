# Legacy tests (quarantined)

These tests target the original `talent_agent.*` package that was replaced by
the FastAPI backend under `backend/app/`. They import modules that no longer
exist (`talent_agent.agents.matcher`, `talent_agent.models`) and fail at
pytest collection time.

They are excluded via `tests/conftest.py` (`collect_ignore_glob`) so the
suite can collect cleanly while we triage them. To re-enable, port the
imports to the new backend layout (see `backend/app/services/match_service.py`,
`backend/app/services/jd_parser.py`, `backend/app/schemas/agent_models.py`)
and move the file back to `tests/`.
