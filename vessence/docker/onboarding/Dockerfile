# ── Onboarding — first-run setup wizard ─────────────────────────────────────
# Exposes port 3000. Runs only until .env is written; after that, stays up
# as a settings/management page.
FROM python:3.13-alpine

LABEL org.opencontainers.image.title="Vessence Onboarding"
LABEL org.opencontainers.image.description="First-run setup wizard for Vessence"
LABEL org.opencontainers.image.source="https://github.com/vessence/vessence"

RUN apk add --no-cache curl

WORKDIR /app

COPY onboarding/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && pip uninstall -y pip 2>/dev/null; true

COPY onboarding/ ./onboarding/

RUN mkdir -p /app/logs /app/vault /app/data

ENV AMBIENT_HOME=/app
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:3000/health || exit 1

CMD ["python", "-m", "uvicorn", "onboarding.main:app", "--host", "0.0.0.0", "--port", "3000"]
