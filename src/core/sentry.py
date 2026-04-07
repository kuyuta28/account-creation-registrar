"""
sentry.py — Sentry SDK initialization (pure function, no-op nếu DSN rỗng).

Single Responsibility: khởi tạo Sentry với đầy đủ integrations.
Được gọi 1 lần duy nhất tại server lifespan startup.
"""
from __future__ import annotations

import logging

from ..config.settings import SentryConfig

_LOG = logging.getLogger("app.sentry")


def init_sentry(cfg: SentryConfig) -> None:
    """Khởi tạo Sentry SDK. Tự động no-op nếu DSN rỗng."""
    if not cfg.dsn:
        _LOG.debug("Sentry DSN not configured — skipping initialization")
        return

    import sentry_sdk
    from sentry_sdk.integrations.asyncio import AsyncioIntegration
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    sentry_sdk.init(
        dsn=cfg.dsn,
        environment=cfg.environment,
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
            AsyncioIntegration(),
            LoggingIntegration(
                level=logging.WARNING,   # breadcrumb từ WARNING trở lên
                event_level=logging.ERROR,  # tạo Sentry event từ ERROR trở lên
            ),
        ],
        traces_sample_rate=cfg.traces_sample_rate,
        profiles_sample_rate=cfg.profiles_sample_rate,
        send_default_pii=cfg.send_default_pii,
    )
    _LOG.info("Sentry initialized (env=%s, traces=%.2f)", cfg.environment, cfg.traces_sample_rate)
