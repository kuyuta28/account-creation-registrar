# syntax=docker/dockerfile:1.7
# registrar: account-creation orchestrator + browser automation.
# Runs headless by default; override via config or env per registrar docs.

FROM python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203 AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    XDG_CACHE_HOME=/app/.cache \
    PLAYWRIGHT_BROWSERS_PATH=/app/.cache/ms-playwright

WORKDIR /build
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential gcc curl git \
 && rm -rf /var/lib/apt/lists/*

COPY common/pyproject.toml ./common/pyproject.toml
COPY common/src ./common/src
RUN pip install --no-cache-dir ./common

COPY registrar/pyproject.toml ./
COPY registrar/src ./src
COPY registrar/main.py ./main.py
COPY registrar/run_api.py ./run_api.py
RUN pip install --no-cache-dir .

RUN playwright install chromium

ARG CAMOUFOX_CACHE_PATH=""
RUN if [ -n "$CAMOUFOX_CACHE_PATH" ] && [ -d "$CAMOUFOX_CACHE_PATH" ]; then \
      mkdir -p /app/.cache/camoufox \
      && cp -r "$CAMOUFOX_CACHE_PATH"/* /app/.cache/camoufox/ ; \
    fi

# --- runtime ---------------------------------------------------------------
FROM python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203 AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    XDG_CACHE_HOME=/app/.cache \
    PLAYWRIGHT_BROWSERS_PATH=/app/.cache/ms-playwright \
    REGISTRAR_HOST=0.0.0.0 \
    REGISTRAR_PORT=8709 \
    PYTHONPATH=/app/common/src:/app/src

RUN groupadd --system --gid 1001 app \
 && useradd --system --uid 1001 --gid app --home-dir /app --shell /usr/sbin/nologin app \
 && mkdir -p /app/.cache /app/data /app/logs /app/debug /app/screenshots /tmp/app \
 && chown -R app:app /app

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder --chown=app:app /app/.cache /app/.cache

RUN apt-get update \
 && apt-get install -y --no-install-recommends wget curl ca-certificates \
 && python -m playwright install-deps chromium \
 && rm -rf /var/lib/apt/lists/* /tmp/*

COPY --chown=app:app common/src ./common/src
COPY --chown=app:app registrar/src ./src
COPY --chown=app:app registrar/main.py ./main.py
COPY --chown=app:app registrar/run_api.py ./run_api.py

VOLUME ["/app/data", "/app/logs", "/app/debug", "/app/screenshots"]
USER app
EXPOSE 8709

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD wget -qO- http://127.0.0.1:8709/api/v1/health || exit 1

ARG SERVICE_NAME="registrar"
ARG SERVICE_VERSION="0.0.0"
ARG BUILD_DATE="1970-01-01T00:00:00Z"
ARG VCS_REF="HEAD"

LABEL org.opencontainers.image.title="${SERVICE_NAME}" \
      org.opencontainers.image.description="registrar for the account-creation platform" \
      org.opencontainers.image.version="${SERVICE_VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.source="https://github.com/kuyuta28/account-creation" \
      org.opencontainers.image.licenses="UNLICENSED" \
      org.opencontainers.image.vendor="kuyuta28"

CMD ["python", "run_api.py"]
