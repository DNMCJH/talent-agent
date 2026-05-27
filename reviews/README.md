# Reviews

## Current Review Gate

- Scope: deep code security and growth
- File: `reviews/2026-05-28_deep_code_security_and_growth.md`
- Status: **Approved for local-to-server sync**
- Round 1 applied: C1, C2, I1, I2, I3, I6, I8, I9, I10, M1, M2 (10)
- Round 2 applied: N1 (.env.example weak placeholders), N2 (placeholder list + min-length), I9-followup (projects.py str(e) leaks), N3 (legacy tests quarantined + smoke test added)
- Round 3 applied: explicit `APP_ENV=production` gate in `Settings` + both compose files + `.env.example`; smoke regression guards the APP_DOMAIN-only-deploy footgun
- Deferred with rationale (5): I4 (OAuth vault), I5 (JWT→cookie), I7 (chunked upload + proxy cap), M3 (AUTH_TRUST_HOST docs), M4 (port legacy test content)
- Verification: `python -m compileall -q backend/app` passed; Codex `py_compile` passed; `python -m pytest -q` passed (`4 passed in 0.07s`)
- Next: sync only after user confirmation; during sync verify server `.env` uses real non-placeholder `POSTGRES_PASSWORD`, `API_SECRET`, and `AUTH_SECRET`
