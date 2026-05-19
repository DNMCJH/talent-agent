#!/usr/bin/env bash
# Smoke test for talent-agent Phase 1 backend.
# Prereqs: docker engine running in WSL (run install_docker_wsl.sh first).
# Run in WSL: bash scripts/smoke_test.sh

set -euo pipefail

# Re-add docker group for this shell (in case usermod -aG hasn't propagated)
if ! groups | grep -q docker; then
  echo "WARN: current shell doesn't have docker group. Either:"
  echo "  - re-open WSL shell (recommended), or"
  echo "  - prefix every docker command with sudo"
  echo
fi

# Detect docker prefix
if docker ps >/dev/null 2>&1; then
  DOCKER="docker"
elif sudo -n docker ps >/dev/null 2>&1; then
  DOCKER="sudo docker"
else
  echo "ERROR: docker not callable. Run: sudo service docker start"
  exit 1
fi
echo "Using: $DOCKER"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
echo "PROJECT_ROOT=$ROOT"

# Step 0: .env bootstrap
if [ ! -f .env ]; then
  echo "=== [0] Creating .env from .env.example ==="
  cp .env.example .env
  # Auto-generate API_SECRET
  SECRET="$(head -c 48 /dev/urandom | base64 | tr -d '/+=' | head -c 48)"
  if grep -q '^API_SECRET=' .env; then
    sed -i "s|^API_SECRET=.*|API_SECRET=${SECRET}|" .env
  else
    echo "API_SECRET=${SECRET}" >> .env
  fi
  echo "Generated random API_SECRET in .env"
fi

echo
echo "=== [1] docker compose up -d --build ==="
$DOCKER compose up -d --build

echo
echo "=== [2] Waiting for postgres to become healthy ==="
PG_CID=""
for i in $(seq 1 30); do
  PG_CID="$($DOCKER compose ps -q postgres 2>/dev/null || true)"
  [ -n "$PG_CID" ] && break
  sleep 1
done
if [ -z "$PG_CID" ]; then
  echo "WARN: cannot find postgres container id; skipping health wait"
else
  for i in $(seq 1 60); do
    STATUS="$($DOCKER inspect -f '{{.State.Health.Status}}' "$PG_CID" 2>/dev/null || echo missing)"
    if [ "$STATUS" = "healthy" ]; then
      echo "postgres healthy after ${i}s"
      break
    fi
    sleep 1
  done
fi

echo
echo "=== [3] Waiting for backend /health ==="
for i in $(seq 1 60); do
  if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    echo "backend up after ${i}s"
    break
  fi
  sleep 1
done

echo
echo "=== [4] Alembic: autogenerate + upgrade ==="
HOST_VERSIONS_DIR="$ROOT/backend/alembic/versions"
mkdir -p "$HOST_VERSIONS_DIR"
HAS_LOCAL_REV="$(ls "$HOST_VERSIONS_DIR"/*.py 2>/dev/null | head -1 || true)"
if [ -z "$HAS_LOCAL_REV" ]; then
  $DOCKER compose exec -T backend alembic revision --autogenerate -m "initial schema"
  BACKEND_CID="$($DOCKER compose ps -q backend)"
  echo "Copying generated migration out to host repo..."
  $DOCKER cp "$BACKEND_CID:/app/alembic/versions/." "$HOST_VERSIONS_DIR/"
  ls "$HOST_VERSIONS_DIR"
else
  echo "Host already has revision(s): $HAS_LOCAL_REV — skipping autogenerate"
fi
$DOCKER compose exec -T backend alembic upgrade head

echo
echo "=== [5] Verify tables in postgres ==="
$DOCKER compose exec -T postgres psql -U talent -d talent -c "\dt"

echo
echo "=== [6] Endpoint smoke checks ==="
echo "--- GET /health ---"
curl -sS http://localhost:8000/health; echo
echo "--- GET /auth/me (expect 401) ---"
curl -sS -o /tmp/out.json -w "HTTP %{http_code}\n" http://localhost:8000/auth/me; cat /tmp/out.json; echo
echo "--- POST /match (expect 501) ---"
curl -sS -o /tmp/out.json -w "HTTP %{http_code}\n" -X POST http://localhost:8000/match -H 'content-type: application/json' -d '{"jd":"test","project_ids":[]}'; cat /tmp/out.json; echo

echo
echo "=== DONE ==="
echo "Acceptance:"
echo "  [ ] $DOCKER compose ps → 4 containers Up"
echo "  [ ] /health → {\"status\":\"ok\"}"
echo "  [ ] \\dt → 5 tables (users/projects/interview_sessions/weaknesses/alembic_version)"
echo "  [ ] /auth/me without token → 401"
echo "  [ ] /match → 501"
