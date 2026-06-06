from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM — default provider (DeepSeek)
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"

    # LLM — relay providers (fucheers OpenAI-compatible relay)
    relay_base_url: str = "https://www.fucheers.top/v1"
    relay_claude_api_key: str = ""
    relay_claude_model: str = "claude-sonnet-4-6"
    relay_gpt_api_key: str = ""
    relay_gpt_model: str = "gpt-4.1"

    # Which provider to use by default: "deepseek" | "claude" | "gpt"
    default_llm_provider: str = "deepseek"

    # Embedding
    embed_model: str = "BAAI/bge-small-zh-v1.5"
    embed_device: str = "cpu"

    # Qdrant (multi-tenant via payload filter on user_id)
    qdrant_url: str = "http://qdrant:6333"
    qdrant_api_key: str = ""
    qdrant_collection_projects: str = "projects"
    qdrant_collection_jds: str = "jds"

    # Postgres (users, projects, sessions, weaknesses)
    postgres_dsn: str = "postgresql+asyncpg://talent:talent@postgres:5432/talent"

    # Redis (session cache, rate limit)
    redis_url: str = "redis://redis:6379/0"

    # GitHub OAuth (verified on the API; UI uses NextAuth.js)
    github_client_id: str = ""
    github_client_secret: str = ""
    github_token: str = ""

    # Deployment classification. Explicit production signal — when set to
    # "production" the placeholder/short-secret checks below hard-fail regardless
    # of `api_public_base` shape. Belt-and-suspenders for the case where the
    # operator sets APP_DOMAIN/Compose but forgets to update API_PUBLIC_BASE.
    app_env: str = "development"

    # API
    api_cors_origins: list[str] = ["http://localhost:3000"]
    api_secret: str = "dev-secret-change-me"  # JWT signing for session tokens
    api_public_base: str = "http://localhost:3000"  # for building email verification links
    talent_agent_token: str = ""  # shared internal token for SpeakFlow callbacks

    # Email (Resend). Leave api key empty to disable email sending (registration
    # still works, users are marked unverified but allowed to use the app).
    resend_api_key: str = ""
    resend_from: str = "Talent Agent <onboarding@resend.dev>"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()


# Known placeholder secrets that must be rejected in production. Includes the
# legacy default plus every example value ever shipped in .env.example, so a
# user who copies the example and forgets to rotate cannot accidentally deploy.
_PLACEHOLDER_API_SECRETS = {
    "dev-secret-change-me",
    "change-me-to-a-long-random-string",
    "REPLACE_WITH_A_LONG_RANDOM_SECRET_AT_LEAST_32_CHARS",
}
# Substrings that look like placeholders even when users edit them slightly.
_PLACEHOLDER_API_SECRET_SUBSTRINGS = ("change-me", "changeme", "replace_with", "placeholder")
_MIN_PROD_SECRET_LENGTH = 32


def _looks_like_prod(public_base: str) -> bool:
    """Heuristic — anything that is not localhost / 127.x is treated as
    production. Useful as a fallback when APP_ENV is unset, but not sufficient
    on its own: APP_DOMAIN-only deployments may still leave API_PUBLIC_BASE
    pointing at localhost. Always combine with the explicit `APP_ENV` signal."""
    base = public_base.lower()
    return not (
        base.startswith("http://localhost")
        or base.startswith("https://localhost")
        or base.startswith("http://127.")
        or base.startswith("https://127.")
    )


def _is_production(app_env: str, public_base: str) -> bool:
    """Combine the explicit APP_ENV signal with the URL heuristic — either
    catches a production deployment so a missed env var on one side does not
    silently let placeholders ship."""
    return app_env.lower() == "production" or _looks_like_prod(public_base)


def _is_placeholder_secret(secret: str) -> bool:
    """Reject obvious placeholder values regardless of exact match — copying
    .env.example and adding a few characters should still be caught."""
    if secret in _PLACEHOLDER_API_SECRETS:
        return True
    lowered = secret.lower()
    return any(needle in lowered for needle in _PLACEHOLDER_API_SECRET_SUBSTRINGS)


_is_prod = _is_production(settings.app_env, settings.api_public_base)

if _is_prod:
    if _is_placeholder_secret(settings.api_secret):
        raise RuntimeError(
            "API_SECRET looks like a placeholder. It signs JWTs, email "
            "verification tokens, password reset tokens, and SSE stream tokens — "
            "set a strong random value in .env (e.g. `python -c \"import secrets; "
            "print(secrets.token_urlsafe(48))\"`) before running in production "
            f"(APP_ENV={settings.app_env!r}, API_PUBLIC_BASE={settings.api_public_base!r})."
        )
    if len(settings.api_secret) < _MIN_PROD_SECRET_LENGTH:
        raise RuntimeError(
            f"API_SECRET is too short ({len(settings.api_secret)} chars). "
            f"Require at least {_MIN_PROD_SECRET_LENGTH} chars in production."
        )
elif _is_placeholder_secret(settings.api_secret):
    import warnings
    warnings.warn(
        "API_SECRET looks like a placeholder — set it in .env before deploying!",
        stacklevel=1,
    )
