# Backend image: the six-agent graph plus the FastAPI bridge.
#
# The web console is built separately (see Dockerfile.frontend) because it is a static
# bundle and has no reason to carry a Python runtime around with it.

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first so a code change does not invalidate the install layer.
COPY requirements.txt ./
COPY webapp/backend/requirements.txt ./webapp/backend/requirements.txt
RUN pip install --upgrade pip \
 && pip install -r requirements.txt \
 && pip install -r webapp/backend/requirements.txt

# Only what the runtime actually needs. The frontend, docs and node_modules stay out.
COPY graph.py llm.py policy.py observability.py audit_log.py ./
COPY agents/ ./agents/
COPY tools/ ./tools/
COPY prompts/ ./prompts/
COPY data/ ./data/
COPY rag/ ./rag/
COPY eval/ ./eval/
COPY stream/ ./stream/
COPY integrations/ ./integrations/
COPY scripts/ ./scripts/
COPY tests/ ./tests/
COPY webapp/backend/ ./webapp/backend/

# Run as a non-root user. This container reaches out to a model provider and, if Slack is
# configured, receives webhooks, so it should not be root for the sake of a demo.
RUN useradd --create-home --uid 1000 tos \
 && mkdir -p /app/logs \
 && chown -R tos:tos /app
USER tos

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "main:app", "--app-dir", "webapp/backend", "--host", "0.0.0.0", "--port", "8000"]
