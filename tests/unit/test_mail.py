"""
unit/test_mail.py — Tests cho src/mail/

Bao phủ:
  - _base.py: random_string, provider_kind, provider_display_name, auth_headers
  - client.py: extract_link, _normalize_providers, _rotated_providers,
               circuit breaker functions, create_mailbox (async), wait_for_message (async)

Pattern: AAA, async tests dùng pytest-asyncio hoặc asyncio.run
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── src/mail/_base.py ─────────────────────────────────────────────────────────

class TestRandomString:
    def test_length(self):
        from src.mail._base import random_string
        assert len(random_string(10)) == 10

    def test_default_length(self):
        from src.mail._base import random_string
        assert len(random_string()) == 12

    def test_charset_lowercase_alphanum(self):
        from src.mail._base import random_string
        s = random_string(100)
        assert all(c in "abcdefghijklmnopqrstuvwxyz0123456789" for c in s)

    def test_unique_outputs(self):
        from src.mail._base import random_string
        results = {random_string(16) for _ in range(30)}
        assert len(results) > 5


class TestAuthHeaders:
    def test_bearer_format(self):
        from src.mail._base import auth_headers
        h = auth_headers("my-token-123")
        assert h["Authorization"] == "Bearer my-token-123"

    def test_returns_dict(self):
        from src.mail._base import auth_headers
        assert isinstance(auth_headers("tok"), dict)


class TestProviderKind:
    def test_mailslurp_prefix(self):
        from src.mail._base import provider_kind
        assert provider_kind("mailslurp_legacy.local:some-key") == "mailslurp_legacy.local"

    def test_testmail_prefix(self):
        from src.mail._base import provider_kind
        assert provider_kind("testmail.app:ns:key") == "testmail.app"

    def test_mail_tm_url(self):
        from src.mail._base import provider_kind
        assert provider_kind("https://api.mail.tm") == "mail.tm"

    def test_mail_gw_url(self):
        from src.mail._base import provider_kind
        assert provider_kind("https://api.mail.gw") == "mail.tm"


class TestProviderDisplayName:
    def test_mailslurp_truncates_key(self):
        from src.mail._base import provider_display_name
        name = provider_display_name("mailslurp_legacy.local:abcdef1234567890")
        assert "mailslurp_legacy.local:..." in name
        assert "34567890" in name

    def test_testmail_shows_namespace(self):
        from src.mail._base import provider_display_name
        name = provider_display_name("testmail.app:im4vw:some-uuid")
        assert "testmail.app:im4vw" in name

    def test_mail_tm_strips_https(self):
        from src.mail._base import provider_display_name
        name = provider_display_name("https://api.mail.tm")
        assert "https://" not in name
        assert "api.mail.tm" in name


# ── src/mail/client.py — pure + async ────────────────────────────────────────

class TestExtractLink:
    """extract_link() — pure regex function."""

    def test_finds_single_url(self):
        from src.mail.client import extract_link
        body = "Click: https://elevenlabs.io/verify?token=abc thanks"
        assert extract_link(body, "verify") == "https://elevenlabs.io/verify?token=abc"

    def test_filters_by_contains(self):
        from src.mail.client import extract_link
        body = "https://other.com/page and https://elevenlabs.io/verify?t=1"
        assert extract_link(body, "elevenlabs") == "https://elevenlabs.io/verify?t=1"

    def test_returns_none_when_no_match(self):
        from src.mail.client import extract_link
        assert extract_link("no links here", "verify") is None

    def test_returns_none_empty_body(self):
        from src.mail.client import extract_link
        assert extract_link("", "verify") is None

    def test_returns_first_url_when_no_filter(self):
        from src.mail.client import extract_link
        body = "https://a.com and https://b.com"
        assert extract_link(body) == "https://a.com"

    def test_filter_is_case_insensitive(self):
        from src.mail.client import extract_link
        body = "https://ELEVENLABS.IO/verify"
        assert extract_link(body, "elevenlabs") is not None


class TestNormalizeProviders:
    def test_strips_trailing_slashes(self):
        from src.mail.client import _normalize_providers
        result = _normalize_providers(["https://api.mail.tm/"])
        assert "https://api.mail.tm" in result

    def test_deduplicates(self):
        from src.mail.client import _normalize_providers
        result = _normalize_providers(["https://api.mail.tm", "https://api.mail.tm"])
        assert len(result) == 1

    def test_raises_when_empty(self):
        from src.mail.client import _normalize_providers
        # empty list → unique is empty → raises
        with pytest.raises(RuntimeError, match="No temp mail"):
            _normalize_providers([])

    def test_raises_when_all_whitespace(self):
        from src.mail.client import _normalize_providers
        # all-whitespace items → filtered out → empty → raises
        with pytest.raises(RuntimeError, match="No temp mail"):
            _normalize_providers(["  ", "", "   "])

    def test_raises_when_none(self):
        from src.mail import client
        with patch("src.mail.client.get_mail_tm_bases", return_value=("https://api.mail.tm",)):
            result = client._normalize_providers(None)
        assert result == ("https://api.mail.tm",)

    def test_returns_tuple(self):
        from src.mail.client import _normalize_providers
        result = _normalize_providers(["https://api.mail.tm"])
        assert isinstance(result, tuple)


class TestRotatedProviders:
    def test_returns_all_providers(self):
        from src.mail.client import _rotated_providers
        providers = ["https://api.mail.tm", "https://api.mail.gw"]
        result = _rotated_providers(providers)
        assert set(result) == set(providers)
        assert len(result) == 2

    def test_returns_tuple(self):
        from src.mail.client import _rotated_providers
        assert isinstance(_rotated_providers(["https://api.mail.tm"]), tuple)

    def test_rotates_start_index(self):
        from src.mail.client import _rotated_providers
        providers = ["a", "b", "c"]
        r1 = _rotated_providers(providers)
        r2 = _rotated_providers(providers)
        # consecutive calls MUST start from different provider
        assert r1[0] != r2[0]


class TestCircuitBreaker:
    """Circuit breaker state — module-level mutable, clear before each test."""

    def setup_method(self):
        """Reset circuit breaker state trước mỗi test."""
        from src.mail import client
        client._provider_fail_counts.clear()
        client._provider_cooldown_until.clear()

    def test_provider_starts_up(self):
        from src.mail.client import _is_provider_down
        assert _is_provider_down("https://api.mail.tm") is False

    def test_mark_fail_increments_count(self):
        from src.mail.client import _mark_provider_fail
        from src.mail import client
        _mark_provider_fail("https://api.mail.tm", cooldown_sec=120, max_fails=3)
        assert client._provider_fail_counts.get("https://api.mail.tm") == 1

    def test_mark_fail_trips_after_max(self):
        from src.mail.client import _mark_provider_fail, _is_provider_down
        for _ in range(3):
            _mark_provider_fail("https://api.mail.tm", cooldown_sec=120, max_fails=3)
        assert _is_provider_down("https://api.mail.tm") is True

    def test_mark_ok_clears_state(self):
        from src.mail.client import _mark_provider_fail, _mark_provider_ok, _is_provider_down
        for _ in range(3):
            _mark_provider_fail("https://api.mail.tm", cooldown_sec=120, max_fails=3)
        _mark_provider_ok("https://api.mail.tm")
        assert _is_provider_down("https://api.mail.tm") is False

    def test_cooldown_expires_after_deadline(self):
        """Simulate cooldown expiry by backdating deadline."""
        import time
        from src.mail import client
        from src.mail.client import _is_provider_down
        client._provider_cooldown_until["https://api.mail.tm"] = time.monotonic() - 1
        assert _is_provider_down("https://api.mail.tm") is False


class TestCreateMailboxAsync:
    """create_mailbox() — async, test với mocked providers."""

    def setup_method(self):
        from src.mail import client
        client._provider_fail_counts.clear()
        client._provider_cooldown_until.clear()

    def test_returns_mailbox_on_success(self):
        from src.mail.client import create_mailbox
        from src.mail._base import Mailbox

        fake_box = Mailbox(
            email="test@mail.tm",
            token="tok",
            account_id="acc",
            base_url="https://api.mail.tm",
            provider="mail.tm",
        )

        async def _run():
            with patch("src.mail.client._create_mailbox_on_provider", new_callable=AsyncMock) as m:
                m.return_value = fake_box
                return await create_mailbox(["https://api.mail.tm"])

        box = asyncio.run(_run())
        assert box.email == "test@mail.tm"

    def test_failover_to_second_provider(self):
        from src.mail.client import create_mailbox
        from src.mail._base import Mailbox

        good_box = Mailbox(
            email="box@mail.gw",
            token="tok",
            account_id="acc",
            base_url="https://api.mail.gw",
            provider="mail.tm",
        )

        async def _run():
            async def fake_create(provider, log_fn=None):
                if provider == "https://api.mail.tm":
                    raise RuntimeError("rate limited")
                return good_box

            with patch("src.mail.client._create_mailbox_on_provider", side_effect=fake_create):
                return await create_mailbox(["https://api.mail.tm", "https://api.mail.gw"])

        box = asyncio.run(_run())
        assert box.email == "box@mail.gw"


class TestWaitForMessageAsync:
    """wait_for_message() — async, test với mocked providers."""

    def _make_box(self, provider="mail.tm"):
        from src.mail._base import Mailbox
        return Mailbox(
            email="test@example.com",
            token="tok",
            account_id="acc",
            base_url="https://api.mail.tm",
            provider=provider,
        )

    def test_returns_none_on_timeout(self):
        from src.mail.client import wait_for_message

        async def _run():
            box = self._make_box()
            with patch("src.mail.providers.mail_tm.wait_for_message", new_callable=AsyncMock) as m:
                m.return_value = None
                return await wait_for_message(box, timeout=1, poll_interval=1)

        result = asyncio.run(_run())
        assert result is None

    def test_returns_message_on_match(self):
        from src.mail.client import wait_for_message

        msg = {
            "id": "msg-1",
            "from": {"address": "no-reply@elevenlabs.io"},
            "subject": "Verify your email",
            "body": "https://elevenlabs.io/verify?token=abc",
        }

        async def _run():
            box = self._make_box()
            with patch("src.mail.providers.mail_tm.wait_for_message", new_callable=AsyncMock) as m:
                m.return_value = msg
                return await wait_for_message(box, from_contains="elevenlabs", timeout=10)

        result = asyncio.run(_run())
        assert result is not None
        assert result["id"] == "msg-1"
