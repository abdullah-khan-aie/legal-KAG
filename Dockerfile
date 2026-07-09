# syntax=docker/dockerfile:1
# Lodestone API + KAG pipeline.
#
# Base image is pinned via the PYTHON_IMAGE arg and shared by both stages so
# they can't drift apart. For strict, auditable reproducibility, override it
# with a digest at build time:
#   docker build --build-arg PYTHON_IMAGE=python:3.13-slim@sha256:<digest> .
ARG PYTHON_IMAGE=python:3.13-slim

# --- builder: resolve dependencies + project into /app/.venv --------------- #
FROM ${PYTHON_IMAGE} AS builder

# Pin uv for reproducible builds; bump deliberately (or pin by digest).
ARG UV_VERSION=0.11.28

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

COPY --from=ghcr.io/astral-sh/uv:${UV_VERSION} /uv /usr/local/bin/uv

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Dependencies first (they change rarely) so this layer caches independently of
# the source. The uv cache is a BuildKit cache mount, so wheels are reused
# across rebuilds instead of re-downloaded.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY kag ./kag
COPY src ./src
COPY Frontend ./Frontend
COPY legal_schema.yaml ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


# --- runtime: minimal image, no build tools, non-root ---------------------- #
FROM ${PYTHON_IMAGE} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 appuser

COPY --from=builder --chown=appuser:appuser /app /app

RUN mkdir -p /data/ingest \
    && chown -R appuser:appuser /data

# Bake the (small, static) ingest corpus into the image so it ships to EC2 via
# ECR -- no host file transfer needed on the SSM-only instance. The directory
# scanner reads this path at ingest time (scan_dir / LODESTONE_SCAN_DIR=/data/ingest).
# Do NOT mount a volume over /data/ingest or it will shadow these files.
COPY --chown=appuser:appuser ingest_docs/ /data/ingest/

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/docs >/dev/null || exit 1

CMD ["uvicorn", "src.lodestone.main:app", "--host", "0.0.0.0", "--port", "8080"]
