# syntax=docker/dockerfile:1
# Multi-stage build: builder → runtime
# Service: perenoska (FastAPI)

# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy dependency manifest first for layer caching
COPY pyproject.toml ./

# Install dependencies into a local prefix (compiled C-extensions included)
RUN pip install --upgrade pip \
    && pip install --prefix=/install . \
    && pip install --prefix=/install ".[dev]"

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Copy compiled site-packages from builder — no gcc in runtime
COPY --from=builder /install /usr/local

# Non-root user for security
RUN useradd --no-create-home --shell /bin/false appuser

WORKDIR /app

# Copy application code
COPY app/ ./app/

# Data directory for SQLite
RUN mkdir -p /app/data && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
