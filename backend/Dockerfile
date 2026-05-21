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
# Install runtime deps from pyproject.toml — single source of truth, so the
# image cannot drift from the declared dependency set. The package itself is
# not built (tool.uv package = false); app/ is copied below.
RUN uv pip install --system -r pyproject.toml

# Bake the embedding model into the image so startup works with HF_HUB_OFFLINE=1.
# An empty hf_cache named volume is seeded from this path on first creation, so
# the model survives the volume mount. Must match EMBED_MODEL in .env.
ENV HF_HOME=/app/.cache/huggingface
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5')"

COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

ENV PYTHONPATH=/app

EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
