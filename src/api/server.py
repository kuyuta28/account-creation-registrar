"""
server.py - FastAPI app entry point.
Service-based: moi domain la 1 router rieng, doc lap.
Response format: unified ApiResponse envelope (schemas.py).
"""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from .exceptions import (
    AppError,
    app_error_handler,
    generic_error_handler,
    http_exception_handler,
    validation_error_handler,
)
from .routers import accounts, aa_proxy, config, gmail, image_lab, internal, mailbox, providers, registration, sms
from ..api.services.job_manager import JobManager
from ..api.services.image_lab_job_manager import ImageLabJobManager
from common.context import init_app_context
from .schemas import ok
from .ws.log_manager import get_bus, set_event_loop
from common.logger import install_tee
from common.sentry import init_sentry
from common.database._engine import init_async_db
from common.middleware import add_request_id_middleware, add_tracing_middleware
from common.tracing import init_tracing
from ..config.settings import load_config, seed_mail_providers

# CORS origins: load từ config, có thể override qua API_CORS_ORIGINS (CSV)
_app_cfg = load_config()
_cors_from_env = os.getenv("API_CORS_ORIGINS")
_CORS_ORIGINS: list[str] = (
    _cors_from_env.split(",")
    if _cors_from_env
    else list(_app_cfg.api.cors_origins)
)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    _cfg = load_config()
    install_tee(_cfg.base_dir, _cfg.log.all_log)
    init_sentry(_cfg.sentry)
    # Init async PostgreSQL if database_url configured
    if _cfg.database.database_url:
        init_async_db(_cfg.database.database_url)
    seed_mail_providers(_cfg)
    # Init AppContext with JobManager
    job_state = JobManager(
        max_jobs=_cfg.registration.max_jobs,
        max_workers=_cfg.registration.max_workers,
    )
    image_lab_manager = ImageLabJobManager(max_jobs=_cfg.registration.max_jobs)
    init_app_context(config=_cfg, db_engine=None, job_state=job_state, image_lab_manager=image_lab_manager)
    set_event_loop(get_bus(), asyncio.get_running_loop())
    yield


app = FastAPI(
    title="Account Creator API",
    version="1.0.0",
    lifespan=_lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── Exception handlers ────────────────────────────────────────────────────────
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, generic_error_handler)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Tracing & Request ID ──────────────────────────────────────────────────────
add_request_id_middleware(app)
add_tracing_middleware(app)
init_tracing("registrar")

# ── Routers ───────────────────────────────────────────────────────────────────
_V1 = "/api/v1"
app.include_router(accounts.router,     prefix=_V1)
app.include_router(registration.router, prefix=_V1)
app.include_router(config.router,       prefix=_V1)
app.include_router(mailbox.router,      prefix=_V1)
app.include_router(providers.router,    prefix=_V1)
app.include_router(image_lab.router,    prefix=_V1)
app.include_router(aa_proxy.router,     prefix=_V1)
app.include_router(gmail.router,        prefix=_V1)
app.include_router(sms.router,          prefix=_V1)
app.include_router(internal.router,    prefix=_V1)


@app.get("/api/v1/health", tags=["system"])
def health():
    return ok({"status": "ok"})