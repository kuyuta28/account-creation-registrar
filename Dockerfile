# syntax=docker/dockerfile:1.7
# --- builder ---------------------------------------------------------------
FROM python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203 AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential gcc \
 && rm -rf /var/lib/apt/lists/*

COPY registrar/pyproject.toml ./pyproject.toml
COPY common/src ./common/src
RUN pip install --no-cache-dir \
        "fastapi>=0.111.0" "uvicorn[standard]>=0.30.0" "httpx>=0.25.0" \
        "pydantic>=2.0.0" "PyYAML>=6.0" "sqlalchemy>=2.0" "asyncpg>=0.29.0" \
        "requests>=2.31.0" "aiofiles>=23.0.0" "Pillow>=10.0.0" "pyotp>=2.9.0" \
        "camoufox>=0.4.0" "playwright>=1.50.0" "patchright>=1.50.0" \
        "sentry-sdk[fastapi]>=2.0.0"

COPY registrar/src ./src
COPY registrar/main.py ./main.py
COPY registrar/run_api.py ./run_api.py

# --- runtime ---------------------------------------------------------------
FROM python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203 AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    REGISTRAR_HOST=0.0.0.0 \
    REGISTRAR_PORT=8709 \
    PYTHONPATH=/app/common/src:/app/src

RUN groupadd --system --gid 1001 app \
 && useradd  --system --uid 1001 --gid app --no-create-home --shell /usr/sbin/nologin app \
 && apt-get update \
 && apt-get install -y --no-install-recommends wget curl ca-certificates fonts-liberation libasound2 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libxkbcommon0 libpango-1.0-0 libcairo2 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY --chown=app:app registrar/src ./src
COPY --chown=app:app registrar/main.py ./main.py
COPY --chown=app:app registrar/run_api.py ./run_api.py
COPY --chown=app:app common/src ./common/src

# Playwright + patchright browser binaries (system deps already in runtime image)
USER root
RUN pip install --no-cache-dir playwright patchright \
 && playwright install chromium \
 && patchright install chromium \
 && rm -rf /var/cache/ms-playwright/* /root/.cache /tmp/*

RUN mkdir -p /app/data /app/logs /app/debug /app/screenshots /tmp/app \
 && chown -R app:app /app/data /app/logs /app/debug /app/screenshots /tmp/app
VOLUME ["/app/data", "/app/logs", "/app/debug", "/app/screenshots"]

USER app
EXPOSE 8709

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD wget -qO- http://127.0.0.1:8709/api/health || exit 1

# OCI image metadata
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
