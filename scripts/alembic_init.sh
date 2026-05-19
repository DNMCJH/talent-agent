#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

HOST_VERSIONS_DIR="$(pwd)/backend/alembic/versions"
mkdir -p "$HOST_VERSIONS_DIR"

HAS_REV="$(ls "$HOST_VERSIONS_DIR"/*.py 2>/dev/null | head -1 || true)"
if [ -z "$HAS_REV" ]; then
  echo "=== autogenerate initial schema ==="
  docker compose exec -T backend alembic revision --autogenerate -m "initial schema"
  BACKEND_CID="$(docker compose ps -q backend)"
  echo "=== copying migration files to host ==="
  docker cp "$BACKEND_CID:/app/alembic/versions/." "$HOST_VERSIONS_DIR/"
  ls -la "$HOST_VERSIONS_DIR"
else
  echo "host already has $HAS_REV; skipping autogenerate"
fi

echo "=== upgrade head ==="
docker compose exec -T backend alembic upgrade head

echo "=== \\dt ==="
docker compose exec -T postgres psql -U talent -d talent -c "\dt"
