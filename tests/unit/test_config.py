"""
unit/test_config.py — Tests cho src/config/settings.py

Bao phủ:
  - MailConfig: expansion shorthands, providers_for, per_service
  - load_config: yaml loading, defaults, per_service parsed
  - _load_raw: merge multiple yaml files
  - TimeoutConfig, AppConfig defaults
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.config.settings import (
    AppConfig,
    AuthSyncConfig,
    LeonardoConfig,
    MailConfig,
    TimeoutConfig,
    load_config,
    _load_raw,
)


# ── MailConfig DB-driven providers_for ───────────────────────────────────────

class TestMailConfigProviders:
    """Tests cho MailConfig.providers_for() — DB-driven, no more static per_service."""

    def _mail(self, db_path=None):
        from pathlib import Path
        return MailConfig(db_path=db_path or Path("data/accounts.db"))

    def test_providers_for_returns_db_results(self):
        from unittest.mock import patch
        mail = self._mail()
        mock_rows = [
            {"connection_str": "testmail.app:ns:uuid-key"},
            {"connection_str": "mailslurp.com:sk_abc"},
        ]
        with patch("src.core.database.get_mail_providers", return_value=mock_rows):
            result = mail.providers_for("testmail")
        assert "testmail.app:ns:uuid-key" in result
        assert "mailslurp.com:sk_abc" in result

    def test_providers_for_returns_empty_when_db_empty(self):
        from unittest.mock import patch
        mail = self._mail()
        with patch("src.core.database.get_mail_providers", return_value=[]):
            result = mail.providers_for()
        assert result == ()  # DB empty → empty tuple (providers seeded via config)

    def test_providers_for_returns_empty_on_db_error(self):
        from unittest.mock import patch
        mail = self._mail()
        with patch("src.core.database.get_mail_providers", side_effect=Exception("DB error")):
            result = mail.providers_for()
        assert result == ()  # DB error → empty tuple

    def test_all_providers_uses_providers_for(self):
        from unittest.mock import patch
        mail = self._mail()
        mock_rows = [{"connection_str": "mailslurp.com:sk_key"}]
        with patch("src.core.database.get_mail_providers", return_value=mock_rows):
            assert mail.all_providers == ("mailslurp.com:sk_key",)

    def test_service_tag_passed_to_db(self):
        from unittest.mock import patch
        mail = self._mail()
        with patch("src.core.database.get_mail_providers", return_value=[]) as mock_db:
            mail.providers_for("chatgpt")
        _args, kwargs = mock_db.call_args
        assert kwargs.get("service_tag") == "chatgpt"

    def test_case_insensitive_service_tag(self):
        from unittest.mock import patch
        mail = self._mail()
        with patch("src.core.database.get_mail_providers", return_value=[]) as mock_db:
            mail.providers_for("ChatGPT")
        _args, kwargs = mock_db.call_args
        assert kwargs.get("service_tag") == "chatgpt"

    def test_no_service_passes_none(self):
        from unittest.mock import patch
        mail = self._mail()
        with patch("src.core.database.get_mail_providers", return_value=[]) as mock_db:
            mail.providers_for()
        _args, kwargs = mock_db.call_args
        assert kwargs.get("service_tag") is None



# ── _load_raw ─────────────────────────────────────────────────────────────────

class TestLoadRaw:
    def _write(self, cfg_dir: Path, filename: str, content: str):
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / filename).write_text(content, encoding="utf-8")

    def test_merges_multiple_yaml_files(self, tmp_path):
        cfg_dir = tmp_path / "config"
        self._write(cfg_dir, "config.yaml", "browser:\n  headless: true\n")
        self._write(cfg_dir, "logging.yaml", "log:\n  append: false\n")
        raw = _load_raw(tmp_path)
        assert raw["browser"]["headless"] is True
        assert raw["log"]["append"] is False

    def test_later_file_overrides_earlier(self, tmp_path):
        """logging.yaml đứng sau config.yaml trong _CONFIG_FILES → override."""
        cfg_dir = tmp_path / "config"
        self._write(cfg_dir, "config.yaml", "log:\n  append: true\n")
        self._write(cfg_dir, "logging.yaml", "log:\n  append: false\n")
        raw = _load_raw(tmp_path)
        assert raw["log"]["append"] is False

    def test_returns_empty_dict_when_no_config_folder(self, tmp_path):
        raw = _load_raw(tmp_path)
        assert raw == {}

    def test_ignores_missing_files(self, tmp_path):
        cfg_dir = tmp_path / "config"
        self._write(cfg_dir, "mail.yaml", "mail:\n  cooldown_sec: 60\n")
        raw = _load_raw(tmp_path)
        assert raw["mail"]["cooldown_sec"] == 60

    def test_empty_yaml_treated_as_empty_dict(self, tmp_path):
        cfg_dir = tmp_path / "config"
        self._write(cfg_dir, "config.yaml", "")
        raw = _load_raw(tmp_path)
        assert raw == {}


# ── load_config ───────────────────────────────────────────────────────────────

class TestLoadConfig:
    def _write_config(self, tmp_path: Path, yaml_text: str) -> Path:
        cfg_dir = tmp_path / "config"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "config.yaml").write_text(yaml_text, encoding="utf-8")
        return cfg_dir / "config.yaml"

    def test_loads_browser_headless(self, tmp_path):
        cfg_path = self._write_config(tmp_path, "browser:\n  headless: true\n")
        cfg = load_config(cfg_path)
        assert cfg.headless is True

    def test_loads_timeouts(self, tmp_path):
        cfg_path = self._write_config(tmp_path, "timeouts:\n  email_wait: 60\n  page_load: 10000\n")
        cfg = load_config(cfg_path)
        assert cfg.timeouts.email_wait == 60
        assert cfg.timeouts.page_load == 10000

    def test_loads_leonardo_config(self, tmp_path):
        yaml_text = (
            "leonardo:\n"
            "  login_url: https://app.leonardo.ai/auth/login\n"
            "  verification_sender: contact@leonardo.ai\n"
            "  otp_wait_sec: 240\n"
        )
        cfg_path = self._write_config(tmp_path, yaml_text)
        cfg = load_config(cfg_path)
        assert cfg.leonardo.login_url == "https://app.leonardo.ai/auth/login"
        assert cfg.leonardo.verification_sender == "contact@leonardo.ai"
        assert cfg.leonardo.otp_wait_sec == 240

    def test_loads_auth_sync(self, tmp_path):
        yaml_text = f"auth_sync:\n  enabled: true\n  target_dir: {tmp_path}/external\n"
        cfg_path = self._write_config(tmp_path, yaml_text)
        cfg = load_config(cfg_path)
        assert cfg.auth_sync.enabled is True
        assert "external" in str(cfg.auth_sync.target_dir)

    # test_loads_mail_providers removed (providers now DB-driven)

    def test_mail_cooldown_parsed(self, tmp_path):
        yaml_text = "mail:\n  cooldown_sec: 90\n  max_consecutive_fails: 5\n"
        cfg_path = self._write_config(tmp_path, yaml_text)
        cfg = load_config(cfg_path)
        assert cfg.mail.cooldown_sec == 90
        assert cfg.mail.max_consecutive_fails == 5

    def test_returns_defaults_on_missing_config(self, tmp_path):
        cfg = load_config(tmp_path / "config" / "config.yaml")
        assert cfg.log.append is False
        assert cfg.timeouts.email_wait == 120

    def test_loads_openrouter_config(self, tmp_path):
        yaml_text = (
            "openrouter:\n"
            "  signup_url: https://openrouter.ai/sign-up\n"
            "  turnstile_sitekey: custom-sitekey\n"
        )
        cfg_path = self._write_config(tmp_path, yaml_text)
        cfg = load_config(cfg_path)
        assert cfg.openrouter.signup_url == "https://openrouter.ai/sign-up"
        assert cfg.openrouter.turnstile_sitekey == "custom-sitekey"

    def test_loads_register_api_key_label(self, tmp_path):
        cfg_path = self._write_config(tmp_path, "register:\n  api_key_label: my-label\n")
        cfg = load_config(cfg_path)
        assert cfg.register.api_key_label == "my-label"


# ── TimeoutConfig defaults ────────────────────────────────────────────────────

class TestTimeoutConfig:
    def test_all_defaults_positive(self):
        t = TimeoutConfig()
        assert t.email_wait > 0
        assert t.page_load > 0
        assert t.poll_interval > 0
        assert t.step_delay > 0
        assert t.click_delay > 0

    def test_no_otp_wait_sec_field(self):
        """otp_wait_sec sống ở per-service configs, KHÔNG phải TimeoutConfig."""
        t = TimeoutConfig()
        assert not hasattr(t, "otp_wait_sec")

    def test_custom_values(self):
        t = TimeoutConfig(email_wait=60, page_load=10000)
        assert t.email_wait == 60
        assert t.page_load == 10000


# ── AppConfig ─────────────────────────────────────────────────────────────────

class TestAppConfig:
    def test_default_instantiation(self):
        cfg = AppConfig()
        assert cfg.headless is False
        assert cfg.viewport_width == 1280
        assert cfg.viewport_height == 720

    def test_all_service_configs_have_urls(self):
        cfg = AppConfig()
        assert cfg.elevenlabs.signup_url.startswith("https://")
        assert cfg.chatgpt.oauth_authorize_url.startswith("https://")
        assert cfg.openrouter.signup_url.startswith("https://")
        assert cfg.leonardo.login_url.startswith("https://")

    def test_dir_properties(self):
        cfg = AppConfig()
        assert cfg.screenshot_dir == cfg.base_dir / "screenshots"
        assert cfg.debug_dir == cfg.base_dir / "debug"

    def test_chatgpt_otp_wait_sec_on_chatgpt_config_not_timeouts(self):
        """Verify otp_wait_sec ada di per-service config, bukan di TimeoutConfig."""
        cfg = AppConfig()
        assert hasattr(cfg.chatgpt, "otp_wait_sec")
        assert not hasattr(cfg.timeouts, "otp_wait_sec")
