"""
smoke/test_imports.py — Verify tất cả modules import không lỗi.

Smoke tests: chạy < 2s, không cần network, không cần file nào.
Mục đích: detect circular imports, missing deps, syntax errors ngay khi push.

Pattern: mỗi test là 1 import statement — rõ ràng, fail message cụ thể.
"""
from __future__ import annotations

import pytest


# ── core + config ─────────────────────────────────────────────────────────────

def test_import_settings():
    from src.config import settings  # noqa


def test_import_load_config():
    from src.config.settings import load_config, AppConfig  # noqa


def test_import_core_database():
    from src.core import database  # noqa


def test_import_core_storage():
    from src.core import storage  # noqa


def test_import_core_password():
    from src.core import password  # noqa


def test_import_core_logger():
    from src.core import logger  # noqa


def test_import_core_page_utils():
    from src.core import page_utils  # noqa


def test_import_core_browser():
    from src.core import browser  # noqa


# ── mail ──────────────────────────────────────────────────────────────────────

def test_import_mail_base():
    from src.mail import _base  # noqa


def test_import_mail_client():
    from src.mail import client  # noqa


def test_import_mail_providers_mail_tm():
    from src.mail.providers import mail_tm  # noqa


def test_import_mail_providers_mailslurp():
    from src.mail.providers import mailslurp_com  # noqa


def test_import_mail_providers_testmail():
    from src.mail.providers import testmail_app  # noqa


# ── captcha ───────────────────────────────────────────────────────────────────

def test_import_capsolver():
    from src.captcha import capsolver  # noqa


def test_import_patchright_solver():
    from src.captcha import patchright_solver  # noqa


# ── services/registry ─────────────────────────────────────────────────────────

def test_import_registry():
    from src.services import registry  # noqa


def test_import_protocols():
    from src.services import protocols  # noqa


def test_import_supported_services_non_empty():
    from src.services.registry import SUPPORTED_SERVICES
    assert len(SUPPORTED_SERVICES) > 0


def test_import_make_registrar_callable():
    from src.services.registry import make_registrar
    assert callable(make_registrar)


# ── services ──────────────────────────────────────────────────────────────────

def test_import_elevenlabs_registrar():
    from src.services.elevenlabs_io import registrar  # noqa


def test_import_elevenlabs_captcha():
    from src.services.elevenlabs_io import captcha  # noqa


def test_import_elevenlabs_api_key():
    from src.services.elevenlabs_io import api_key  # noqa


def test_import_openrouter_registrar():
    from src.services.openrouter_ai import registrar  # noqa


def test_import_leonardo_registrar():
    from src.services.leonardo_ai import registrar  # noqa


def test_import_proton_registrar():
    from src.services.proton_me import registrar  # noqa


def test_import_artificialanalysis_registrar():
    from src.services.artificialanalysis_ai import registrar  # noqa


def test_import_testmail_registrar():
    from src.services.testmail_app import registrar  # noqa


# ── checkers ──────────────────────────────────────────────────────────────────

def test_import_checkers_base():
    from src.checkers import base  # noqa


def test_import_checkers_chatgpt():
    from src.checkers import chatgpt  # noqa


def test_import_checkers_elevenlabs():
    from src.checkers import elevenlabs  # noqa


def test_import_checkers_openrouter():
    from src.checkers import openrouter  # noqa


# ── API ───────────────────────────────────────────────────────────────────────

def test_import_api_server():
    from src.api import server  # noqa


def test_import_api_routers_registration():
    from src.api.routers import registration  # noqa


def test_import_api_routers_accounts():
    from src.api.routers import accounts  # noqa


def test_import_api_services_registration():
    from src.api.services import registration_service  # noqa


def test_import_api_services_account():
    from src.api.services import account_service  # noqa


def test_import_api_services_mailbox():
    from src.api.services import mailbox_service  # noqa


def test_import_api_ws_log_manager():
    from src.api.ws import log_manager  # noqa


# ── cli ───────────────────────────────────────────────────────────────────────

def test_import_cli_runners():
    from src.cli import runners  # noqa


def test_import_cli_menu():
    from src.cli import menu  # noqa


# ── config loads with defaults ────────────────────────────────────────────────

def test_default_appconfig_instantiates():
    """AppConfig() không cần yaml file — tất cả defaults hoạt động."""
    from src.config.settings import AppConfig
    cfg = AppConfig()
    assert cfg.timeouts.email_wait == 120
    assert cfg.timeouts.page_load == 20_000
    assert cfg.elevenlabs.signup_url.startswith("https://")
    assert cfg.chatgpt.oauth_authorize_url.startswith("https://")


def test_all_registry_services_have_callable_factories():
    """Mỗi service trong registry phải trả callable khi gọi make_registrar."""
    from src.config.settings import AppConfig
    from src.services.registry import SUPPORTED_SERVICES, make_registrar

    cfg = AppConfig()
    for svc in SUPPORTED_SERVICES:
        r = make_registrar(svc, cfg)
        assert callable(r), f"{svc}: make_registrar returned non-callable"
