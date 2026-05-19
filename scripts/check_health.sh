#!/usr/bin/env bash
set -uo pipefail
for i in $(seq 1 30); do
  if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    echo "up after ${i}s"
    curl -s http://localhost:8000/health
    echo
    break
  fi
  sleep 1
done
echo '---last logs---'
cd "$(dirname "$0")/.."
docker compose logs backend --tail=15
