"""Smoke tests — keep the suite non-empty so `pytest -q` exits 0 even after
the legacy tests are quarantined, and guard the C2 placeholder-secret check.

Tests here MUST NOT import modules that pull in runtime deps (redis, qdrant,
sentence-transformers, etc.) — that lets `pytest` run from the repo root
without the backend venv. Heavier integration tests belong in a separate file
that the backend venv runs.
"""

import sys
from pathlib import Path

# Tests run from the repo root; make the `backend/` source tree importable.
_BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def test_config_module_imports() -> None:
    """`app.core.config` is a leaf module — must import on bare Python so the
    placeholder check below is exercisable in any environment."""
    import app.core.config  # noqa: F401


def test_placeholder_secret_detection() -> None:
    """Guard the explicit placeholder list and substring heuristic so the
    next .env.example edit cannot regress C2."""
    from app.core.config import _is_placeholder_secret

    assert _is_placeholder_secret("dev-secret-change-me")
    assert _is_placeholder_secret("change-me-to-a-long-random-string")
    assert _is_placeholder_secret("REPLACE_WITH_A_LONG_RANDOM_SECRET_AT_LEAST_32_CHARS")
    assert _is_placeholder_secret("my-changeme-secret-123")  # substring catch
    assert _is_placeholder_secret("totally_placeholder_value_x")
    assert not _is_placeholder_secret("k3J2pQ8vR7nM4xL9zT6yB1wA5fH0sD")


def test_prod_detection_heuristic() -> None:
    """`_looks_like_prod` must let localhost dev through and gate everything
    else into prod-validation."""
    from app.core.config import _looks_like_prod

    assert not _looks_like_prod("http://localhost:3000")
    assert not _looks_like_prod("https://localhost")
    assert not _looks_like_prod("http://127.0.0.1:8000")
    assert _looks_like_prod("https://projfit.top")
    assert _looks_like_prod("http://example.com")


def test_app_env_overrides_url_heuristic() -> None:
    """APP_ENV=production must classify as prod even when API_PUBLIC_BASE is
    still localhost (the APP_DOMAIN-only deploy footgun Codex flagged in
    round-2 verify). Conversely, APP_ENV=development with a localhost base
    must stay in dev mode."""
    from app.core.config import _is_production

    # APP_ENV=production wins regardless of base URL
    assert _is_production("production", "http://localhost:3000")
    assert _is_production("PRODUCTION", "http://localhost:3000")  # case-insensitive
    # URL heuristic still catches deploys that set base but forget APP_ENV
    assert _is_production("development", "https://projfit.top")
    # Pure local dev — neither signal trips
    assert not _is_production("development", "http://localhost:3000")
    assert not _is_production("", "http://127.0.0.1:8000")
