FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# uv: fast Python package installer
COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /usr/local/bin/uv

WORKDIR /app

# install CPU-only torch first to keep image lean (sentence-transformers will pull it otherwise)
RUN uv pip install --system --index-url https://download.pytorch.org/whl/cpu torch==2.4.1+cpu

COPY pyproject.toml ./
# Install runtime deps only (no build of this package — app/ is mounted/copied below)
RUN uv pip install --system \
    "fastapi>=0.115.0" "uvicorn[standard]>=0.32.0" "httpx>=0.27.0" "pyjwt>=2.9.0" \
    "sqlalchemy[asyncio]>=2.0.35" "asyncpg>=0.30.0" "alembic>=1.13.0" "redis>=5.1.0" \
    "qdrant-client>=1.12.0" "sentence-transformers>=3.0.0" \
    "openai>=1.50.0" "pydantic>=2.9.0" "pydantic-settings>=2.5.0" "gitpython>=3.1.40"

COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic

ENV PYTHONPATH=/app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
