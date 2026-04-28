FROM python:3.12-slim

WORKDIR /app

# Install system deps for playwright/camoufox/patchright
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install playwright browser
RUN pip install --no-cache-dir playwright patchright \
    && playwright install chromium --with-deps

# Copy project files
COPY registrar/pyproject.toml ./pyproject.toml
COPY registrar/src ./src
COPY registrar/main.py .
COPY registrar/run_api.py .
COPY common/src ./common/src

# Install dependencies (exclude common since it's local)
RUN pip install --no-cache-dir -e . --no-deps

# Install remaining dependencies
RUN pip install --no-cache-dir fastapi uvicorn httpx pydantic PyYAML sqlalchemy requests aiofiles Pillow pyotp camoufox playwright sentry-sdk

# Create directories
RUN mkdir -p /app/data /app/logs /app/debug /app/screenshots

EXPOSE 8709

ENV REGISTRAR_HOST=0.0.0.0
ENV REGISTRAR_PORT=8709
ENV PYTHONPATH=/app/common/src

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD wget -qO- http://localhost:8709/api/health || exit 1

CMD ["python", "run_api.py"]
