# ── MAYA — Production Dockerfile (AWS App Runner) ────────────────────────────
# Base: python:3.12-slim  (~130 MB) — no Ollama, no voice, web-only
# Port: 8080 (App Runner default)
# DB:   PostgreSQL via DATABASE_URL env var (SQLite not used in production)
# ──────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim

# System deps: curl (health check) + libpq (psycopg2 runtime)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Layer 1: dependencies (cached unless requirements-web.txt changes) ────────
COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt

# ── Layer 2: application source ───────────────────────────────────────────────
COPY src/ src/

# ── Runtime config ────────────────────────────────────────────────────────────
# These are defaults only — override via App Runner environment variables.
# Never bake real secrets into the image.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

EXPOSE 8080

# Health check — App Runner polls /health every 30 s
# Fail after 3 consecutive misses (90 s total) before marking unhealthy
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# ── Entrypoint ────────────────────────────────────────────────────────────────
CMD ["uvicorn", "src.maya.web.app:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--workers", "1"]