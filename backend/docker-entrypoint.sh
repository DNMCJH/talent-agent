#!/usr/bin/env sh
# Run pending DB migrations before starting the API server.
# This is the single source of truth for VPS schema — manual ALTER TABLEs
# are no longer needed because every schema change ships as an alembic rev.
set -e

echo "[entrypoint] Running alembic upgrade head…"
alembic upgrade head

echo "[entrypoint] Starting uvicorn…"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
