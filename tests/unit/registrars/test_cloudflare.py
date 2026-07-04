
"""tests/unit/registrars/test_cloudflare.py - Unit tests for Cloudflare registrar helpers."""
from __future__ import annotations

from pathlib import Path

from src.config.settings import AppConfig, CloudflareConfig, load_config
from src.services.registry import SUPPORTED_SERVICES, make_registrar


class TestRegistry:
    def test_cloudflare_in_supported_services(self):
        assert "CLOUDFLARE" in SUPPORTED_SERVICES

    def test_make_registrar_resolves_cloudflare(self):
        cfg = AppConfig()
        registrar = make_registrar("CLOUDFLARE", cfg)
        assert registrar is not None


class TestPureHelpers:
    def _call_extract_account_id(self, url: str):
        from src.services.cloudflare_com.registrar import _extract_account_id
        return _extract_account_id(
            url,
            r'dash\.cloudflare\.com/([0-9a-f]{32})/',
        )

    def test_extract_account_id_from_token_url(self):
        url = "https://dash.cloudflare.com/5852b6460a6e72c85a4107cec04a749d/api-tokens/create"
        assert self._call_extract_account_id(url) == "5852b6460a6e72c85a4107cec04a749d"

    def test_extract_account_id_none_when_no_match(self):
        assert self._call_extract_account_id("https://example.com/abc") is None

    def _call_extract_api_token(self, text: str):
        from src.services.cloudflare_com.registrar import _extract_api_token
        return _extract_api_token(text, r'[A-Za-z0-9_-]{40,}')

    def test_extract_api_token(self):
        token = "a1b2c3d4e5f6789012345678901234567890abcd"
        assert self._call_extract_api_token(f"Your API Token\n{token}") == token

    def test_extract_api_token_none_for_short(self):
        assert self._call_extract_api_token("short") is None

    def _call_build_token_url(self, account_id: str):
        from src.services.cloudflare_com.registrar import _build_token_create_url
        return _build_token_create_url(
            account_id,
            "https://dash.cloudflare.com/{account_id}/api-tokens/create",
        )

    def test_build_token_create_url(self):
        assert (
            self._call_build_token_url("5852b6460a6e72c85a4107cec04a749d")
            == "https://dash.cloudflare.com/5852b6460a6e72c85a4107cec04a749d/api-tokens/create"
        )


class TestConfigLoad:
    def test_cloudflare_config_defaults_are_valid(self):
        cfg = CloudflareConfig()
        assert cfg.signup_url == "https://dash.cloudflare.com/sign-up"
        assert cfg.token_create_url_template == "https://dash.cloudflare.com/{account_id}/api-tokens/create"
        assert "AI" in cfg.ai_section_name

    def test_load_config_includes_cloudflare(self):
        # load from the actual configured path expecting defaults to be present
        cfg = load_config(Path("D:/business/account-creation/registrar/config/config.yaml"))
        assert cfg.cloudflare.signup_url.startswith("https://")
