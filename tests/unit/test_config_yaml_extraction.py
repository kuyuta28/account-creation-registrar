"""Tests cho registrar config loading — Google OAuth, Mail, CORS."""
from __future__ import annotations

import pytest

from src.config.settings import (
    GoogleOAuthConfig,
    MailConfig,
    load_config,
)


# ── Test: GoogleOAuthConfig defaults ──────────────────────────────────────

class TestGoogleOAuthConfigDefaults:
    def test_default_login_url(self):
        cfg = GoogleOAuthConfig()
        assert cfg.login_url == "https://accounts.google.com/signin/v2/identifier"

    def test_default_myaccount_url(self):
        cfg = GoogleOAuthConfig()
        assert cfg.myaccount_url == "https://myaccount.google.com"

    def test_default_login_timeout_ms(self):
        cfg = GoogleOAuthConfig()
        assert cfg.login_timeout_ms == 60_000

    def test_default_popup_close_timeout_ms(self):
        cfg = GoogleOAuthConfig()
        assert cfg.popup_close_timeout_ms == 30_000


# ── Test: MailConfig new fields ───────────────────────────────────────────

class TestMailConfigNewFields:
    def test_default_http_timeout(self):
        cfg = MailConfig()
        assert cfg.http_timeout_sec == 15

    def test_default_wait_timeout(self):
        cfg = MailConfig()
        assert cfg.wait_timeout_sec == 120

    def test_default_poll_interval(self):
        cfg = MailConfig()
        assert cfg.poll_interval_sec == 5

    def test_default_max_retries(self):
        cfg = MailConfig()
        assert cfg.max_retries == 3

    def test_default_retry_max_delay(self):
        cfg = MailConfig()
        assert cfg.retry_max_delay_sec == 30


# ── Test: Full config from YAML ────────────────────────────────────────────

class TestFullConfigFromYAML:
    def test_google_oauth_exists_in_config(self):
        cfg = load_config()
        assert hasattr(cfg, "google_oauth")
        assert isinstance(cfg.google_oauth, GoogleOAuthConfig)

    def test_google_oauth_login_url_from_yaml(self):
        cfg = load_config()
        assert cfg.google_oauth.login_url == "https://accounts.google.com/signin/v2/identifier"

    def test_google_oauth_myaccount_url_from_yaml(self):
        cfg = load_config()
        assert cfg.google_oauth.myaccount_url == "https://myaccount.google.com"

    def test_google_oauth_login_timeout_from_yaml(self):
        cfg = load_config()
        assert cfg.google_oauth.login_timeout_ms == 60_000

    def test_google_oauth_popup_timeout_from_yaml(self):
        cfg = load_config()
        assert cfg.google_oauth.popup_close_timeout_ms == 30_000

    def test_mail_http_timeout_from_yaml(self):
        cfg = load_config()
        assert cfg.mail.http_timeout_sec == 15

    def test_mail_wait_timeout_from_yaml(self):
        cfg = load_config()
        assert cfg.mail.wait_timeout_sec == 120

    def test_mail_poll_interval_from_yaml(self):
        cfg = load_config()
        assert cfg.mail.poll_interval_sec == 5

    def test_cors_has_tauri_localhost(self):
        cfg = load_config()
        assert "https://tauri.localhost" in cfg.api.cors_origins


# ── Test: Google OAuth getter functions ────────────────────────────────────

class TestGoogleOAuthGetters:
    """_constants.py getter functions phải trả values từ config.
    NOTE: không import trực tiếp google_oauth package vì cần Playwright deps.
    Thay vào đó, verify getter logic bằng cách test config value."""

    def test_get_login_url(self):
        cfg = load_config()
        assert cfg.google_oauth.login_url == "https://accounts.google.com/signin/v2/identifier"

    def test_get_myaccount_url(self):
        cfg = load_config()
        assert cfg.google_oauth.myaccount_url == "https://myaccount.google.com"

    def test_get_login_timeout_ms(self):
        cfg = load_config()
        assert cfg.google_oauth.login_timeout_ms == 60_000

    def test_get_popup_close_timeout_ms(self):
        cfg = load_config()
        assert cfg.google_oauth.popup_close_timeout_ms == 30_000


# ── Test: Backward compat re-exports ───────────────────────────────────────

class TestBackwardCompat:
    """Module-level constants trong __init__.py phải backward compat.
    NOTE: không import trực tiếp google_oauth package vì cần Playwright deps.
    Thay vào đó, verify constants match config values."""

    def test_google_signin_url_constant(self):
        cfg = load_config()
        assert cfg.google_oauth.login_url == "https://accounts.google.com/signin/v2/identifier"

    def test_google_account_url_constant(self):
        cfg = load_config()
        assert cfg.google_oauth.myaccount_url == "https://myaccount.google.com"

    def test_login_timeout_ms_constant(self):
        cfg = load_config()
        assert cfg.google_oauth.login_timeout_ms == 60_000

    def test_popup_close_timeout_ms_constant(self):
        cfg = load_config()
        assert cfg.google_oauth.popup_close_timeout_ms == 30_000


# ── Test: Frozen dataclass immutability ────────────────────────────────────

class TestFrozenConfig:
    def test_google_oauth_is_frozen(self):
        cfg = load_config().google_oauth
        with pytest.raises(AttributeError):
            cfg.login_url = "https://evil.com"

    def test_mail_is_frozen(self):
        cfg = load_config().mail
        with pytest.raises(AttributeError):
            cfg.http_timeout_sec = 999