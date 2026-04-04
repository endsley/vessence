# ── Amber — Google ADK agent ────────────────────────────────────────────────
# Exposes port 8000 (ADK dev server).
# Data lives in /app/vault and /app/vector_db, both bind-mounted at runtime.
FROM python:3.13-slim

LABEL org.opencontainers.image.title="Vessence Amber"
LABEL org.opencontainers.image.description="Amber — always-on AI companion (Google ADK)"
LABEL org.opencontainers.image.source="https://github.com/vessence/vessence"

# System deps: git for potential ADK installs, curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl gcc g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer cache)
COPY configs/requirements_adk.txt /tmp/requirements_adk.txt
RUN pip install --no-cache-dir -r /tmp/requirements_adk.txt

# Copy application code (NEVER copy databases, .env, or personal data)
COPY amber/         ./amber/
COPY agent_skills/  ./agent_skills/
COPY jane/          ./jane/
COPY services.py    ./services.py

# Remove any databases or session data that may have been swept in
RUN find /app -name "*.db" -delete && find /app -name "*.sqlite3" -delete \
    && rm -rf /app/amber/.adk/

# Ensure logs and vault dirs exist
RUN mkdir -p /app/logs /app/vault /app/vector_db /app/data /app/credentials

# Environment
ENV AMBIENT_HOME=/app
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# ADK serves on 8000 by default
EXPOSE 8000

# Health check via ADK's built-in endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

CMD ["python", "-m", "google.adk.cli.fast_api", "--host", "0.0.0.0", "--port", "8000", "amber"]
