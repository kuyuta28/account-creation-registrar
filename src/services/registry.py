"""
registry.py — Central registry: service name → Registrar factory.

FP pattern:
  - Pure dict mapping tên service → factory function
  - Factory nhận AppConfig → trả Registrar (partial-applied callable)
  - Lazy import tránh circular dep và heavy startup cost

Public API:
  SUPPORTED_SERVICES      — list tên service được hỗ trợ
  make_registrar(svc, cfg) — trả Registrar hoặc None
"""
from __future__ import annotations

from functools import partial
from collections.abc import Callable

from ..config.settings import AppConfig
from .protocols import Registrar


# ── OpenRouter: fully FP ───────────────────────────────────────────────

def _make_openrouter(cfg: AppConfig) -> Registrar:
    from .openrouter_ai.registrar import register_openrouter
    return partial(register_openrouter, cfg)


def _make_elevenlabs(cfg: AppConfig) -> Registrar:
    from .elevenlabs_io.registrar import register_elevenlabs
    return partial(register_elevenlabs, cfg)


def _make_leonardo(cfg: AppConfig) -> Registrar:
    from .leonardo_ai.registrar import register_leonardo
    return partial(register_leonardo, cfg)


def _make_proton(cfg: AppConfig) -> Registrar:
    from .proton_me.registrar import register_proton
    return partial(register_proton, cfg)


def _make_artificialanalysis(cfg: AppConfig) -> Registrar:
    from .artificialanalysis_ai.registrar import register_artificialanalysis
    return partial(register_artificialanalysis, cfg)


def _make_cloudflare(cfg: AppConfig) -> Registrar:
    from .cloudflare_com.registrar import register_cloudflare
    return partial(register_cloudflare, cfg)


def _make_testmail(cfg: AppConfig) -> Registrar:
    from .testmail_app.registrar import register_testmail
    return partial(register_testmail, cfg)


def _make_mailosaur(cfg: AppConfig) -> Registrar:
    from .mailosaur_com.registrar import register_mailosaur
    return partial(register_mailosaur, cfg)


# ── Registry dict ──────────────────────────────────────────────────────

_FACTORIES: dict[str, Callable[[AppConfig], Registrar]] = {
    "OPENROUTER": _make_openrouter,
    "ELEVENLABS": _make_elevenlabs,
    "LEONARDO":   _make_leonardo,
    "PROTON":     _make_proton,
    "ARTIFICIALANALYSIS": _make_artificialanalysis,
    "CLOUDFLARE":           _make_cloudflare,
    "TESTMAIL":           _make_testmail,
    "MAILOSAUR":          _make_mailosaur,
}

SUPPORTED_SERVICES: list[str] = list(_FACTORIES.keys())


def make_registrar(service: str, cfg: AppConfig) -> Registrar | None:
    """Resolve + instantiate registrar for the given service name."""
    factory = _FACTORIES.get(service.upper())
    if not factory:
        return None
    return factory(cfg)
