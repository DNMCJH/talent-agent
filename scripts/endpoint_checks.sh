#!/usr/bin/env bash
set -uo pipefail

echo "=== /health ==="
curl -sS http://localhost:8000/health; echo

echo "=== /auth/me (expect 401) ==="
curl -sS -o /tmp/o -w "HTTP %{http_code}\n" http://localhost:8000/auth/me
cat /tmp/o; echo

echo "=== /match (expect 401, requires auth) ==="
curl -sS -o /tmp/o -w "HTTP %{http_code}\n" -X POST http://localhost:8000/match \
  -H 'content-type: application/json' -d '{"raw_jd":"test","top_k":3}'
cat /tmp/o; echo

echo "=== /projects (expect 401) ==="
curl -sS -o /tmp/o -w "HTTP %{http_code}\n" http://localhost:8000/projects
cat /tmp/o; echo

echo "=== /docs HEAD ==="
curl -sS -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8000/docs

echo "=== openapi route list ==="
curl -sS http://localhost:8000/openapi.json | python3 -c 'import sys,json; d=json.load(sys.stdin); print("\n".join(sorted(d["paths"].keys())))'
