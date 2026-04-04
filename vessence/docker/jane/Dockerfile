# ── Jane — web UI + standing brain ──────────────────────────────────────────
# Exposes port 8090.
# CLI brain (gemini/claude/openai) installs on first boot based on JANE_BRAIN env var.
# This keeps the image small — only the chosen brain is installed.
FROM python:3.13-slim

LABEL org.opencontainers.image.title="Vessence Jane"
LABEL org.opencontainers.image.description="Jane — your personal AI assistant"
LABEL org.opencontainers.image.source="https://github.com/vessence/vessence"

# Minimal system deps: curl for health checks, ca-certs for HTTPS
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps (trimmed: removes unused transitive deps after install)
# Keep all opentelemetry packages — chromadb imports them at startup.
COPY vault_web/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && pip uninstall -y pip sympy kubernetes pygments \
       2>/dev/null; true

# Copy app code (NEVER copy databases, .env, or personal data)
COPY jane_web/    ./jane_web/
COPY jane/        ./jane/
COPY vault_web/   ./vault_web/
COPY agent_skills/ ./agent_skills/

# Remove any databases that may have been swept in
RUN find /app -name "*.db" -delete && find /app -name "*.sqlite3" -delete

# First-boot CLI installer script
COPY docker/jane/install_brain.sh /app/install_brain.sh
RUN chmod +x /app/install_brain.sh

RUN mkdir -p /app/logs /app/vault /app/data /app/credentials

ENV AMBIENT_HOME=/app
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
# Default brain: gemini (overridden by .env)
ENV JANE_BRAIN=gemini

EXPOSE 8090

HEALTHCHECK --interval=30s --timeout=10s --start-period=300s --retries=3 \
    CMD curl -sf http://localhost:8090/health || exit 1

# First boot: install CLI brain, then start uvicorn
CMD ["/bin/bash", "-c", "/app/install_brain.sh && python -m uvicorn jane_web.main:app --host 0.0.0.0 --port 8090 --proxy-headers --forwarded-allow-ips '*'"]
