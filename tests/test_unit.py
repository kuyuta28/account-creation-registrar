"""
Unit Tests Ã¢â‚¬â€ no network, no browser, no I/O.
All external calls mocked.
"""
from __future__ import annotations

import sys
import os
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

# Make project root importable
_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _ROOT)


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
# src/mail/client.py
# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

class TestRandomString(unittest.TestCase):
    def test_length(self):
        from src.mail._base import random_string
        self.assertEqual(len(random_string(10)), 10)

    def test_charset(self):
        from src.mail._base import random_string
        s = random_string(50)
        self.assertTrue(all(c in "abcdefghijklmnopqrstuvwxyz0123456789" for c in s))

    def test_unique(self):
        from src.mail._base import random_string
        results = {random_string(12) for _ in range(20)}
        self.assertGreater(len(results), 1)


class TestExtractLinks(unittest.TestCase):
    def test_finds_url(self):
        from src.mail.client import extract_link
        body = "Click here: https://elevenlabs.io/verify?token=abc thanks"
        self.assertEqual(extract_link(body, "verify"), "https://elevenlabs.io/verify?token=abc")

    def test_filters_by_contains(self):
        from src.mail.client import extract_link
        body = "https://other.com/page and https://elevenlabs.io/verify?t=1"
        self.assertEqual(extract_link(body, "elevenlabs"), "https://elevenlabs.io/verify?t=1")

    def test_empty_body(self):
        from src.mail.client import extract_link
        self.assertIsNone(extract_link("no links here", "verify"))


class TestCreateMailbox(unittest.TestCase):
    """create_mailbox is async since mail/client.py refactor."""

    def _make_mailbox(self, provider="https://api.mail.tm"):
        from src.mail._base import Mailbox
        return Mailbox(
            email="box@test.example",
            token="tok-abc",
            account_id="acc-123",
            base_url=provider,
        )

    @patch("src.mail.client._mark_provider_ok")
    @patch("src.mail.client._mark_provider_fail")
    @patch("src.mail.client._is_provider_down", return_value=False)
    @patch("src.mail.client._create_mailbox_on_provider", new_callable=AsyncMock)
    def test_create_returns_mailbox(self, mock_create, mock_down, mock_fail, mock_ok):
        import asyncio
        from src.mail.client import create_mailbox

        async def _coro(prov, log_fn=None):
            return self._make_mailbox(prov)
        mock_create.side_effect = _coro
        with patch("builtins.print"):
            mailbox = asyncio.run(create_mailbox(["https://api.mail.tm"]))
        self.assertTrue(mailbox.email.endswith("@test.example"))
        self.assertEqual(mailbox.token, "tok-abc")

    @patch("src.mail.client._create_mailbox_on_provider", new_callable=AsyncMock)
    def test_create_fails_over_to_next_provider(self, mock_create):
        import asyncio
        from src.mail.client import create_mailbox

        call_count = [0]
        async def _side(prov, log_fn=None):
            call_count[0] += 1
            if prov == "https://api.mail.tm":
                raise RuntimeError("rate limited")
            return self._make_mailbox(prov)
        mock_create.side_effect = _side

        with patch("builtins.print"),\
             patch("src.mail.client.random.sample", side_effect=lambda items, k: items),\
             patch("src.mail.client._is_provider_down", return_value=False),\
             patch("src.mail.client._mark_provider_fail"),\
             patch("src.mail.client._mark_provider_ok"):
            mailbox = asyncio.run(create_mailbox(["https://api.mail.tm", "https://api.mail.gw"]))

        self.assertEqual(mailbox.base_url, "https://api.mail.gw")

    def test_raises_when_all_providers_fail(self):
        import asyncio
        from src.mail.client import create_mailbox

        async def _fail(prov, log_fn=None):
            raise RuntimeError("down")

        with patch("src.mail.client._create_mailbox_on_provider", side_effect=_fail),\
             patch("builtins.print"),\
             patch("src.mail.client._is_provider_down", return_value=False),\
             patch("src.mail.client._mark_provider_fail"),\
             patch("src.mail.client._mark_provider_ok"):
            with self.assertRaises(RuntimeError):
                asyncio.run(create_mailbox(["https://api.mail.tm"]))


class TestCircuitBreaker(unittest.TestCase):
    """_mark_provider_fail, _mark_provider_ok, _is_provider_down."""

    def setUp(self):
        from src.mail import client as c
        c._provider_fail_counts.clear()
        c._provider_cooldown_until.clear()

    def test_provider_not_down_initially(self):
        from src.mail.client import _is_provider_down
        self.assertFalse(_is_provider_down("https://api.mail.tm"))

    def test_below_max_fails_not_down(self):
        from src.mail.client import _mark_provider_fail, _is_provider_down
        from src.mail import client as c
        c._provider_fail_counts.clear()
        c._provider_cooldown_until.clear()
        _mark_provider_fail("https://api.mail.tm", cooldown_sec=60, max_fails=3)
        _mark_provider_fail("https://api.mail.tm", cooldown_sec=60, max_fails=3)
        self.assertFalse(_is_provider_down("https://api.mail.tm"))

    def test_at_max_fails_triggers_cooldown(self):
        from src.mail.client import _mark_provider_fail, _is_provider_down
        from src.mail import client as c
        c._provider_fail_counts.clear()
        c._provider_cooldown_until.clear()
        with patch("builtins.print"):
            for _ in range(3):
                _mark_provider_fail("https://api.mail.tm", cooldown_sec=3600, max_fails=3)
        self.assertTrue(_is_provider_down("https://api.mail.tm"))

    def test_mark_ok_clears_cooldown(self):
        from src.mail.client import _mark_provider_fail, _mark_provider_ok, _is_provider_down
        from src.mail import client as c
        c._provider_fail_counts.clear()
        c._provider_cooldown_until.clear()
        with patch("builtins.print"):
            for _ in range(3):
                _mark_provider_fail("h", cooldown_sec=3600, max_fails=3)
        _mark_provider_ok("h")
        self.assertFalse(_is_provider_down("h"))


class TestWaitForMessage(unittest.TestCase):
    def _make_mailbox(self):
        from src.mail._base import Mailbox
        return Mailbox(
            email="test@example.com",
            token="tok-xyz",
            account_id="acc-123",
            base_url="https://api.mail.tm",
        )

    def test_returns_none_on_timeout(self):
        import asyncio
        from src.mail.client import wait_for_message
        from unittest.mock import AsyncMock

        async def _fake_wait(box, from_contains, subject_contains, timeout, poll_interval, log_fn=None):
            return None

        with patch("src.mail.providers.mail_tm.wait_for_message", side_effect=_fake_wait):
            result = asyncio.run(
                wait_for_message(self._make_mailbox(), timeout=1, poll_interval=1)
            )
        self.assertIsNone(result)

    def test_returns_matching_message(self):
        import asyncio
        from src.mail.client import wait_for_message
        from unittest.mock import AsyncMock

        msg = {
            "id": "msg-1",
            "from": {"address": "no-reply@elevenlabs.io"},
            "subject": "Verify your email",
            "body": "https://elevenlabs.io/verify?token=abc",
        }

        async def _fake_wait(box, from_contains, subject_contains, timeout, poll_interval, log_fn=None):
            return msg

        with patch("src.mail.providers.mail_tm.wait_for_message", side_effect=_fake_wait):
            result = asyncio.run(
                wait_for_message(
                    self._make_mailbox(),
                    from_contains="elevenlabs",
                    timeout=10,
                    poll_interval=1,
                )
            )
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "msg-1")

    def test_extract_link_finds_url(self):
        from src.mail.client import extract_link
        link = extract_link("Verify: https://elevenlabs.io/verify?token=xyz", contains="verify")
        self.assertEqual(link, "https://elevenlabs.io/verify?token=xyz")

    def test_extract_link_returns_none_when_empty(self):
        from src.mail.client import extract_link
        self.assertIsNone(extract_link("no links", contains="verify"))

    def test_extract_link_filters_by_contains(self):
        from src.mail.client import extract_link
        body = "https://other.com/page and https://elevenlabs.io/verify?t=1"
        self.assertEqual(extract_link(body, contains="elevenlabs"), "https://elevenlabs.io/verify?t=1")




# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
# src/core/password.py
# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

class TestGeneratePassword(unittest.TestCase):
    def test_length(self):
        from src.core.password import generate_password
        self.assertEqual(len(generate_password(14)), 14)

    def test_has_uppercase(self):
        from src.core.password import generate_password
        for _ in range(20):
            self.assertTrue(any(c.isupper() for c in generate_password(14)))

    def test_has_digit(self):
        from src.core.password import generate_password
        for _ in range(20):
            self.assertTrue(any(c.isdigit() for c in generate_password(14)))

    def test_has_special(self):
        from src.core.password import generate_password
        for _ in range(20):
            self.assertIn("@", generate_password(14))

    def test_min_length(self):
        from src.core.password import generate_password
        self.assertEqual(len(generate_password(8)), 8)


class TestGenerateUsername(unittest.TestCase):
    def test_length(self):
        from src.core.password import generate_username
        self.assertEqual(len(generate_username(17)), 17)

    def test_starts_with_letter(self):
        from src.core.password import generate_username
        for _ in range(20):
            self.assertTrue(generate_username(17)[0].isalpha())

    def test_lowercase_alphanumeric(self):
        from src.core.password import generate_username
        import string
        valid = string.ascii_lowercase + string.digits
        for _ in range(20):
            self.assertTrue(all(c in valid for c in generate_username(17)))


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
# src/core/storage.py
# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

class TestAccountRecord(unittest.TestCase):
    def test_to_json_entry_includes_api_key(self):
        from src.core.storage import AccountRecord, serialize_account_record
        r = AccountRecord(service="ELEVENLABS", email="a@b.com", password="pw", api_key="sk_123")
        d = serialize_account_record(r)
        self.assertEqual(d["email"], "a@b.com")
        self.assertEqual(d["api_key"], "sk_123")
        self.assertNotIn("service", d)

    def test_to_json_entry_omits_empty_api_key(self):
        from src.core.storage import AccountRecord, serialize_account_record
        r = AccountRecord(service="PROTON", email="a@b.com", password="pw")
        self.assertNotIn("api_key", serialize_account_record(r))

    def test_to_json_entry_with_api_key(self):
        from src.core.storage import AccountRecord, serialize_account_record
        entry = serialize_account_record(AccountRecord(service="ELEVENLABS", email="a@b.com", password="pw", api_key="sk_abc"))
        self.assertEqual(entry["email"], "a@b.com")
        self.assertEqual(entry["api_key"], "sk_abc")
        self.assertNotIn("service", entry)

    def test_to_json_entry_without_timestamps(self):
        from src.core.storage import AccountRecord, serialize_account_record
        entry = serialize_account_record(AccountRecord(
            service="CHATGPT",
            email="a@b.com",
            password="pw",
            refresh_token="rt",
            token_type="codex",
        ), include_timestamps=False)
        self.assertNotIn("created_at", entry)
        self.assertNotIn("updated_at", entry)
        self.assertEqual(entry["type"], "codex")


class TestStorageHelpers(unittest.TestCase):
    def test_should_export_codex_auth_true_for_chatgpt_codex(self):
        from src.core.storage import AccountRecord, should_export_codex_auth
        record = AccountRecord(service="CHATGPT", email="a@b.com", password="pw", token_type="codex")
        self.assertTrue(should_export_codex_auth(record))

    def test_should_export_codex_auth_false_for_other_records(self):
        from src.core.storage import AccountRecord, should_export_codex_auth
        record = AccountRecord(service="ELEVENLABS", email="a@b.com", password="pw", token_type="codex")
        self.assertFalse(should_export_codex_auth(record))

    def test_build_codex_auth_path(self):
        from pathlib import Path
        from src.core.storage import build_codex_auth_path
        path = build_codex_auth_path(Path("D:/tmp"), "codex-user@example.com")
        self.assertEqual(str(path).replace("\\", "/"), "D:/tmp/auth/codex-codex-user@example.com-free.json")

    def test_load_json_accepts_utf8_bom(self):
        import tempfile
        from pathlib import Path
        from src.core.storage import load_json

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bom.json"
            path.write_bytes(b"\xef\xbb\xbf" + b'[{\"email\":\"bom@example.com\"}]')
            self.assertEqual(load_json(path)[0]["email"], "bom@example.com")

    def test_write_json_never_writes_utf8_bom(self):
        import tempfile
        from pathlib import Path
        from src.core.storage import write_json

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plain.json"
            write_json(path, [{"email": "plain@example.com"}])
            self.assertFalse(path.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_sync_auth_directory_copies_json_without_bom(self):
        import tempfile
        from pathlib import Path
        from src.core.storage import sync_auth_directory, write_json

        payload = {"email": "codex-user@example.com", "disabled": False, "type": "codex"}
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp) / "repo"
            target_dir = Path(tmp) / "external-auth"
            source_path = base_dir / "auth" / "codex-codex-user@example.com-free.json"
            write_json(source_path, payload)

            synced = sync_auth_directory(base_dir, target_dir)

            self.assertEqual(len(synced), 1)
            target_path = target_dir / source_path.name
            self.assertTrue(target_path.exists())
            self.assertFalse(target_path.read_bytes().startswith(b"\xef\xbb\xbf"))
            self.assertEqual(target_path.read_text(encoding="utf-8").count("codex-user@example.com"), 1)


class TestAccountRepository(unittest.TestCase):
    """Repo + repo_save replaces old AccountRepository."""

    def tearDown(self):
        from src.core.database import _engines
        for key, engine in list(_engines.items()):
            engine.dispose()
        _engines.clear()

    def test_save_writes_to_db(self):
        import tempfile
        from pathlib import Path
        from src.core.storage import AccountRecord, Repo, init_repo, repo_save
        from src.core.database import get_account_by_email

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            repo = Repo(base_dir=Path(tmp))
            init_repo(repo)
            record = AccountRecord(service="ELEVENLABS", email="x@y.com", password="P@1", api_key="sk_xyz")
            repo_save(repo, record)

            acc = get_account_by_email(repo.db, "ELEVENLABS", "x@y.com")
            self.assertIsNotNone(acc)
            self.assertEqual(acc["email"], "x@y.com")
            self.assertEqual(acc["api_key"], "sk_xyz")
            self.assertFalse(acc["disabled"])

    def test_chatgpt_save_writes_codex_auth_file(self):
        import json
        import tempfile
        from pathlib import Path
        from src.core.storage import AccountRecord, Repo, init_repo, repo_save

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            repo = Repo(base_dir=Path(tmp))
            init_repo(repo)
            record = AccountRecord(
                service="CHATGPT",
                email="codex-user@example.com",
                password="P@1",
                refresh_token="rt_123",
                access_token="at_123",
                account_id="acc_123",
                token_type="codex",
            )
            repo_save(repo, record)

            auth_path = Path(tmp) / "auth" / "codex-codex-user@example.com-free.json"
            self.assertTrue(auth_path.exists())
            payload = json.loads(auth_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["email"], "codex-user@example.com")
            self.assertEqual(payload["type"], "codex")
            self.assertFalse(payload["disabled"])
            self.assertNotIn("created_at", payload)
            self.assertNotIn("updated_at", payload)

    def test_chatgpt_save_syncs_codex_auth_file_to_target_dir(self):
        import json
        import tempfile
        from pathlib import Path
        from src.config.settings import AuthSyncConfig
        from src.core.storage import AccountRecord, Repo, init_repo, repo_save

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            base_dir = Path(tmp) / "repo"
            target_dir = Path(tmp) / "external-auth"
            repo = Repo(base_dir=base_dir, auth_sync=AuthSyncConfig(enabled=True, target_dir=target_dir))
            init_repo(repo)
            record = AccountRecord(
                service="CHATGPT",
                email="codex-user@example.com",
                password="P@1",
                refresh_token="rt_123",
                access_token="at_123",
                account_id="acc_123",
                token_type="codex",
                disabled=False,
            )

            repo_save(repo, record)

            target_path = target_dir / "codex-codex-user@example.com-free.json"
            self.assertTrue(target_path.exists())
            payload = json.loads(target_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["email"], "codex-user@example.com")
            self.assertFalse(payload["disabled"])
            self.assertEqual(payload["type"], "codex")
            self.assertFalse(target_path.read_bytes().startswith(b"\xef\xbb\xbf"))


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
# src/config/settings.py
# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

class TestLoadConfig(unittest.TestCase):
    def test_loads_yaml_values(self):
        import tempfile
        from pathlib import Path
        from src.config.settings import load_config

        yaml_text = (
            "log:\n"
            "  append: true\n"
            "browser:\n"
            "  headless: true\n"
            "timeouts:\n"
            "  email_wait: 60\n"
            "  page_load: 10000\n"
            "leonardo:\n"
            "  login_url: https://app.leonardo.ai/auth/login\n"
            "  app_url_contains: app.leonardo.ai\n"
            "  verification_sender: contact@leonardo.ai\n"
            "  otp_wait_sec: 240\n"
            "auth_sync:\n"
            "  enabled: true\n"
            "  target_dir: D:/external/auth\n"
            "mail:\n"
            "  providers:\n"
            "    - mail.tm\n"
            "    - mailslurp.com\n"
            "  per_service:\n"
            "    chatgpt:\n"
            "      - mail.tm\n"
            "    openrouter:\n"
            "      - mailslurp.com\n"
            "  mailslurp_api_keys:\n"
            "    - key-test-abc\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp) / "config"
            cfg_dir.mkdir()
            (cfg_dir / "config.yaml").write_text(yaml_text, encoding="utf-8")
            cfg = load_config(cfg_dir / "config.yaml")
        self.assertTrue(cfg.log.append)
        self.assertTrue(cfg.headless)
        self.assertEqual(cfg.timeouts.email_wait, 60)
        self.assertEqual(cfg.leonardo.login_url, "https://app.leonardo.ai/auth/login")
        self.assertEqual(cfg.leonardo.verification_sender, "contact@leonardo.ai")
        self.assertEqual(cfg.leonardo.otp_wait_sec, 240)
        self.assertEqual(str(cfg.auth_sync.target_dir).replace("\\", "/"), "D:/external/auth")

    def test_returns_defaults_on_empty_config_dir(self):
        import tempfile
        from pathlib import Path
        from src.config.settings import load_config

        with tempfile.TemporaryDirectory() as tmp:
            # No config/ subfolder â†’ _load_raw returns {} â†’ all fields default
            cfg = load_config(Path(tmp) / "config" / "config.yaml")
        self.assertFalse(cfg.log.append)
        self.assertEqual(cfg.timeouts.email_wait, 120)
        self.assertTrue(cfg.auth_sync.enabled)
        self.assertEqual(
            str(cfg.auth_sync.target_dir).replace("\\", "/"),
            "C:/Users/admin/.ccs/cliproxy/auth",
        )
        self.assertEqual(cfg.leonardo.login_url, "https://app.leonardo.ai/auth/login")
        self.assertEqual(cfg.leonardo.verification_sender, "leonardo.ai")


class TestLeonardoHelpers(unittest.TestCase):
    def test_extract_verification_code_from_subject(self):
        from src.services.leonardo_ai.registrar import _extract_verification_code

        code = _extract_verification_code({"subject": "Your Leonardo code is 482913"})

        self.assertEqual(code, "482913")

    def test_extract_verification_code_from_body(self):
        from src.services.leonardo_ai.registrar import _extract_verification_code

        code = _extract_verification_code({"body": "Use 731004 to verify your Leonardo account."})

        self.assertEqual(code, "731004")

    def test_extract_verification_code_returns_none_when_missing(self):
        from src.services.leonardo_ai.registrar import _extract_verification_code

        self.assertIsNone(_extract_verification_code({"body": "No code here"}))

    def test_is_dashboard_true_for_app_page(self):
        from src.services.leonardo_ai.registrar import _is_dashboard

        self.assertTrue(_is_dashboard("https://app.leonardo.ai/home", "app.leonardo.ai"))

    def test_is_dashboard_false_for_auth_page(self):
        from src.services.leonardo_ai.registrar import _is_dashboard

        self.assertFalse(_is_dashboard("https://app.leonardo.ai/auth/login", "app.leonardo.ai"))


class TestChatGPTAboutYouHelpers(unittest.TestCase):
    def test_looks_like_about_you_text_for_birthday_variant(self):
        from src.services.chatgpt_com.page_actions import _looks_like_about_you_text

        text = "Confirm your age\nFull name\nBirthday\nFinish creating account"

        self.assertTrue(_looks_like_about_you_text(text))

    def test_looks_like_about_you_text_for_age_variant(self):
        from src.services.chatgpt_com.page_actions import _looks_like_about_you_text

        text = "How old are you?\nFull name\nAge\nUse date of birth\nFinish creating account"

        self.assertTrue(_looks_like_about_you_text(text))


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# src/services/elevenlabs/captcha.py
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestValidCoord(unittest.TestCase):
    def _vc(self, pt):
        from src.services.elevenlabs_io.captcha import _valid_coord
        return _valid_coord(pt)

    def test_center(self):       self.assertTrue(self._vc({"x": 0.5, "y": 0.5}))
    def test_origin(self):       self.assertTrue(self._vc({"x": 0.0, "y": 0.0}))
    def test_max(self):          self.assertTrue(self._vc({"x": 1.0, "y": 1.0}))
    def test_x_over(self):       self.assertFalse(self._vc({"x": 1.01, "y": 0.5}))
    def test_y_negative(self):   self.assertFalse(self._vc({"x": 0.5, "y": -0.01}))
    def test_missing_x(self):    self.assertFalse(self._vc({"y": 0.5}))
    def test_missing_y(self):    self.assertFalse(self._vc({"x": 0.5}))
    def test_empty_dict(self):   self.assertFalse(self._vc({}))
    def test_not_dict(self):     self.assertFalse(self._vc([0.5, 0.5]))
    def test_string_values(self): self.assertFalse(self._vc({"x": "0.5", "y": "0.5"}))


class TestArea(unittest.TestCase):
    def test_normal(self):
        from src.services.elevenlabs_io.captcha import _area
        self.assertAlmostEqual(_area({"width": 400, "height": 300}), 120_000)

    def test_zero_width(self):
        from src.services.elevenlabs_io.captcha import _area
        self.assertEqual(_area({"width": 0, "height": 300}), 0)


class TestFmtBbox(unittest.TestCase):
    def test_contains_all_fields(self):
        from src.services.elevenlabs_io.captcha import _fmt_bbox
        result = _fmt_bbox({"x": 10, "y": 20, "width": 400, "height": 300})
        for expected in ("10", "20", "400", "300"):
            self.assertIn(expected, result)


class TestFindChallengeBbox(unittest.TestCase):
    def _page(self, bboxes):
        page = AsyncMock()
        elements = []
        for b in bboxes:
            el = AsyncMock()
            el.bounding_box = AsyncMock(return_value=b)
            elements.append(el)
        page.query_selector_all = AsyncMock(return_value=elements)
        return page

    def _cap(self):
        from src.config.settings import CaptchaConfig
        return CaptchaConfig()  # min_w=300, min_h=250

    def test_no_iframes_returns_none(self):
        import asyncio
        from src.services.elevenlabs_io.captcha import _find_challenge_bbox
        self.assertIsNone(asyncio.run(_find_challenge_bbox(self._page([]), self._cap())))

    def test_none_bounding_box_skipped(self):
        import asyncio
        from src.services.elevenlabs_io.captcha import _find_challenge_bbox
        self.assertIsNone(asyncio.run(_find_challenge_bbox(self._page([None]), self._cap())))

    def test_too_small_returns_none(self):
        import asyncio
        from src.services.elevenlabs_io.captcha import _find_challenge_bbox
        self.assertIsNone(asyncio.run(_find_challenge_bbox(
            self._page([{"x": 0, "y": 10, "width": 100, "height": 100}]), self._cap())))

    def test_negative_y_skipped(self):
        import asyncio
        from src.services.elevenlabs_io.captcha import _find_challenge_bbox
        self.assertIsNone(asyncio.run(_find_challenge_bbox(
            self._page([{"x": 0, "y": -5, "width": 400, "height": 300}]), self._cap())))

    def test_valid_iframe_returned(self):
        import asyncio
        from src.services.elevenlabs_io.captcha import _find_challenge_bbox
        bbox = {"x": 0, "y": 10, "width": 400, "height": 300}
        self.assertEqual(asyncio.run(_find_challenge_bbox(self._page([bbox]), self._cap())), bbox)

    def test_returns_largest_of_multiple(self):
        import asyncio
        from src.services.elevenlabs_io.captcha import _find_challenge_bbox
        small = {"x": 0, "y": 0, "width": 300, "height": 250}
        large = {"x": 50, "y": 0, "width": 600, "height": 500}
        self.assertEqual(asyncio.run(_find_challenge_bbox(self._page([small, large]), self._cap())), large)

    def test_exact_min_size_accepted(self):
        import asyncio
        from src.services.elevenlabs_io.captcha import _find_challenge_bbox
        bbox = {"x": 0, "y": 0, "width": 300, "height": 250}  # exactly at min threshold
        self.assertEqual(asyncio.run(_find_challenge_bbox(self._page([bbox]), self._cap())), bbox)

    def test_one_below_min_width_rejected(self):
        import asyncio
        from src.services.elevenlabs_io.captcha import _find_challenge_bbox
        bbox = {"x": 0, "y": 0, "width": 299, "height": 300}
        self.assertIsNone(asyncio.run(_find_challenge_bbox(self._page([bbox]), self._cap())))


class TestExecuteClicks(unittest.TestCase):
    def _deps(self, click_delay_ms=0):
        from src.config.settings import CaptchaConfig
        return AsyncMock(), CaptchaConfig(click_delay_ms=click_delay_ms), MagicMock()

    def test_empty_list_no_mouse_call(self):
        import asyncio
        from src.services.elevenlabs_io.captcha import _execute_clicks
        page, cap, logger = self._deps()
        asyncio.run(_execute_clicks(page, {"x": 0, "y": 0, "width": 400, "height": 300}, [], cap, logger))
        page.mouse.click.assert_not_called()

    def test_single_click_absolute_coords(self):
        import asyncio
        from src.services.elevenlabs_io.captcha import _execute_clicks
        page, cap, logger = self._deps()
        bbox = {"x": 100, "y": 50, "width": 400, "height": 300}
        asyncio.run(_execute_clicks(page, bbox, [{"x": 0.5, "y": 0.5}], cap, logger))
        # abs: 100 + 0.5*400 = 300,  50 + 0.5*300 = 200
        page.mouse.click.assert_called_once_with(300.0, 200.0)

    def test_multiple_clicks_correct_count(self):
        import asyncio
        from src.services.elevenlabs_io.captcha import _execute_clicks
        page, cap, logger = self._deps()
        bbox = {"x": 0, "y": 0, "width": 200, "height": 200}
        clicks = [{"x": 0.25, "y": 0.25}, {"x": 0.75, "y": 0.75}]
        asyncio.run(_execute_clicks(page, bbox, clicks, cap, logger))
        self.assertEqual(page.mouse.click.call_count, 2)
        page.mouse.click.assert_any_call(50.0,  50.0)
        page.mouse.click.assert_any_call(150.0, 150.0)

    def test_top_left_click(self):
        import asyncio
        from src.services.elevenlabs_io.captcha import _execute_clicks
        page, cap, logger = self._deps()
        bbox = {"x": 0, "y": 0, "width": 400, "height": 300}
        asyncio.run(_execute_clicks(page, bbox, [{"x": 0.0, "y": 0.0}], cap, logger))
        page.mouse.click.assert_called_once_with(0.0, 0.0)


class TestClickVerify(unittest.TestCase):
    def _bbox(self):
        return {"x": 0, "y": 0, "width": 400, "height": 300}

    def test_with_btn_uses_llm_coords(self):
        import asyncio
        from src.services.elevenlabs_io.captcha import _click_verify
        page, logger = AsyncMock(), MagicMock()
        asyncio.run(_click_verify(page, self._bbox(), {"x": 0.85, "y": 0.95}, logger))
        # 0.85*400=340,  0.95*300=285
        page.mouse.click.assert_called_once_with(340.0, 285.0)

    def test_without_btn_uses_fallback(self):
        import asyncio
        from src.services.elevenlabs_io.captcha import _click_verify
        page, logger = AsyncMock(), MagicMock()
        asyncio.run(_click_verify(page, self._bbox(), None, logger))
        # fallback: 0.82*400=328,  0.95*300=285
        page.mouse.click.assert_called_once_with(328.0, 285.0)

    def test_with_btn_at_offset_bbox(self):
        import asyncio
        from src.services.elevenlabs_io.captcha import _click_verify
        page, logger = AsyncMock(), MagicMock()
        bbox = {"x": 100, "y": 50, "width": 200, "height": 100}
        asyncio.run(_click_verify(page, bbox, {"x": 0.5, "y": 0.5}, logger))
        # 100 + 0.5*200=200,  50 + 0.5*100=100
        page.mouse.click.assert_called_once_with(200.0, 100.0)


class TestAskLLMAction(unittest.TestCase):
    def _cfg(self):
        from src.config.settings import AppConfig
        return AppConfig()

    def _log(self):
        return MagicMock()

    def _setup_mk(self, mk, content):
        """Set up mock LLM client with async create()."""
        resp = MagicMock()
        resp.choices[0].message.content = content
        mk.return_value.chat.completions.create = AsyncMock(return_value=resp)
        return mk

    @patch("src.services.elevenlabs_io.captcha._make_llm_client")
    def test_click_response_parsed(self, mk):
        import asyncio
        from src.services.elevenlabs_io.captcha import _ask_llm_action
        self._setup_mk(mk, '{"type": "click", "clicks": [{"x": 0.3, "y": 0.4}]}')
        r = asyncio.run(_ask_llm_action("b64", self._cfg(), self._log()))
        self.assertEqual(r["type"], "click")
        self.assertEqual(len(r["clicks"]), 1)
        self.assertAlmostEqual(r["clicks"][0]["x"], 0.3)
        self.assertAlmostEqual(r["clicks"][0]["y"], 0.4)

    @patch("src.services.elevenlabs_io.captcha._make_llm_client")
    def test_drag_response_parsed(self, mk):
        import asyncio
        from src.services.elevenlabs_io.captcha import _ask_llm_action
        self._setup_mk(mk, '{"type": "drag", "drags": [{"from": {"x": 0.8, "y": 0.5}, "to": {"x": 0.3, "y": 0.5}}]}')
        r = asyncio.run(_ask_llm_action("b64", self._cfg(), self._log()))
        self.assertEqual(r["type"], "drag")
        self.assertEqual(len(r["drags"]), 1)
        self.assertAlmostEqual(r["drags"][0]["from"]["x"], 0.8)
        self.assertAlmostEqual(r["drags"][0]["to"]["x"],  0.3)

    @patch("src.services.elevenlabs_io.captcha._make_llm_client")
    def test_no_json_returns_empty_clicks(self, mk):
        import asyncio
        from src.services.elevenlabs_io.captcha import _ask_llm_action
        self._setup_mk(mk, "I cannot help with that.")
        r = asyncio.run(_ask_llm_action("b64", self._cfg(), self._log()))
        self.assertEqual(r["type"], "click")
        self.assertEqual(r["clicks"], [])

    @patch("src.services.elevenlabs_io.captcha._make_llm_client")
    def test_out_of_range_click_filtered(self, mk):
        import asyncio
        from src.services.elevenlabs_io.captcha import _ask_llm_action
        self._setup_mk(mk, '{"type": "click", "clicks": [{"x": 1.5, "y": 0.5}, {"x": 0.3, "y": 0.4}]}')
        r = asyncio.run(_ask_llm_action("b64", self._cfg(), self._log()))
        self.assertEqual(len(r["clicks"]), 1)  # x=1.5 filtered out
        self.assertAlmostEqual(r["clicks"][0]["x"], 0.3)

    @patch("src.services.elevenlabs_io.captcha._make_llm_client")
    def test_invalid_drag_to_coord_filtered(self, mk):
        import asyncio
        from src.services.elevenlabs_io.captcha import _ask_llm_action
        self._setup_mk(mk, '{"type": "drag", "drags": ['
            '{"from": {"x": 0.8, "y": 0.5}, "to": {"x": 1.5, "y": 0.5}},'
            '{"from": {"x": 0.2, "y": 0.3}, "to": {"x": 0.6, "y": 0.7}}'
            ']}')
        r = asyncio.run(_ask_llm_action("b64", self._cfg(), self._log()))
        self.assertEqual(r["type"], "drag")
        self.assertEqual(len(r["drags"]), 1)  # first drag filtered (to.x=1.5)

    @patch("src.services.elevenlabs_io.captcha._make_llm_client")
    def test_llm_exception_returns_none(self, mk):
        import asyncio
        from src.services.elevenlabs_io.captcha import _ask_llm_action
        mk.return_value.chat.completions.create = AsyncMock(side_effect=Exception("timeout"))
        r = asyncio.run(_ask_llm_action("b64", self._cfg(), self._log()))
        self.assertIsNone(r)

    @patch("src.services.elevenlabs_io.captcha._make_llm_client")
    def test_missing_type_defaults_to_click(self, mk):
        import asyncio
        from src.services.elevenlabs_io.captcha import _ask_llm_action
        self._setup_mk(mk, '{"clicks": [{"x": 0.5, "y": 0.5}]}')
        r = asyncio.run(_ask_llm_action("b64", self._cfg(), self._log()))
        self.assertEqual(r["type"], "click")

    @patch("src.services.elevenlabs_io.captcha._make_llm_client")
    def test_empty_clicks_list_accepted(self, mk):
        import asyncio
        from src.services.elevenlabs_io.captcha import _ask_llm_action
        self._setup_mk(mk, '{"type": "click", "clicks": []}')
        r = asyncio.run(_ask_llm_action("b64", self._cfg(), self._log()))
        self.assertEqual(r["type"], "click")
        self.assertEqual(r["clicks"], [])

    @patch("src.services.elevenlabs_io.captcha._make_llm_client")
    def test_json_wrapped_in_markdown_fences(self, mk):
        import asyncio
        from src.services.elevenlabs_io.captcha import _ask_llm_action
        # LLM sometimes wraps JSON in ```json ... ```
        self._setup_mk(mk, '```json\n{"type": "click", "clicks": [{"x": 0.5, "y": 0.5}]}\n```')
        r = asyncio.run(_ask_llm_action("b64", self._cfg(), self._log()))
        self.assertEqual(r["type"], "click")
        self.assertEqual(len(r["clicks"]), 1)

    @patch("src.services.elevenlabs_io.captcha._make_llm_client")
    def test_all_drag_coords_invalid_returns_empty_drags(self, mk):
        import asyncio
        from src.services.elevenlabs_io.captcha import _ask_llm_action
        self._setup_mk(mk, '{"type": "drag", "drags": [{"from": {"x": 2.0, "y": 0.5}, "to": {"x": 0.3, "y": 0.5}}]}')
        r = asyncio.run(_ask_llm_action("b64", self._cfg(), self._log()))
        self.assertEqual(r["type"], "drag")
        self.assertEqual(r["drags"], [])


class TestChatGPTCheckerPersistence(unittest.TestCase):
    def tearDown(self):
        from src.core.database import _engines
        for key, engine in list(_engines.items()):
            engine.dispose()
        _engines.clear()

    def test_persist_refreshed_updates_db_and_auth_exports(self):
        import json
        import tempfile
        from pathlib import Path

        from src.checkers.chatgpt import _persist_refreshed
        from src.config.settings import AppConfig, AuthSyncConfig
        from src.core.storage import AccountRecord, Repo, init_repo, repo_save
        from src.core.database import get_account_by_email

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            base_dir = Path(tmp) / "repo"
            target_dir = Path(tmp) / "external-auth"
            cfg = AppConfig(base_dir=base_dir, auth_sync=AuthSyncConfig(enabled=True, target_dir=target_dir))
            repo = Repo(base_dir=base_dir, auth_sync=cfg.auth_sync)
            init_repo(repo)

            # Insert initial account into DB
            init_record = AccountRecord(
                service="CHATGPT",
                email="codex-user@example.com",
                password="pw",
                refresh_token="old-rt",
                access_token="old-at",
                account_id="old-account",
                token_type="codex",
            )
            repo_save(repo, init_record)

            accounts = [{
                "email": "codex-user@example.com",
                "password": "pw",
                "disabled": False,
                "refresh_token": "old-rt",
                "access_token": "old-at",
                "account_id": "old-account",
                "id_token": "old-id",
                "expired": "2025-01-01T00:00:00+00:00",
                "last_refresh": "2025-01-01T00:00:00+00:00",
                "type": "codex",
            }]
            results = [{
                "valid": True,
                "reason": "",
                "refreshed": {
                    "access_token": "new-at",
                    "refresh_token": "new-rt",
                    "id_token": "new-id",
                    "account_id": "new-account",
                    "expired": "2026-01-01T00:00:00+00:00",
                    "last_refresh": "2026-01-01T00:00:00+00:00",
                },
            }]

            with patch("builtins.print"):
                _persist_refreshed(cfg, repo, accounts, results)

            # Check DB updated
            acc = get_account_by_email(repo.db, "CHATGPT", "codex-user@example.com")
            self.assertIsNotNone(acc)
            self.assertEqual(acc["access_token"], "new-at")
            self.assertEqual(acc["refresh_token"], "new-rt")

            # Check auth file written
            auth_path = base_dir / "auth" / "codex-codex-user@example.com-free.json"
            self.assertTrue(auth_path.exists())
            auth_payload = json.loads(auth_path.read_text(encoding="utf-8"))
            self.assertEqual(auth_payload["access_token"], "new-at")
            self.assertEqual(auth_payload["refresh_token"], "new-rt")
            self.assertFalse(auth_payload["disabled"])
            self.assertNotIn("created_at", auth_payload)
            self.assertNotIn("updated_at", auth_payload)

            # Check synced to target dir
            synced_payload = json.loads(
                (target_dir / "codex-codex-user@example.com-free.json").read_text(encoding="utf-8")
            )
            self.assertEqual(synced_payload["access_token"], "new-at")
            self.assertEqual(synced_payload["refresh_token"], "new-rt")




# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# src/config/settings.py â€” MailConfig.per_service / providers_for / _expand
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestMailConfig(unittest.TestCase):
    def _mail(self, db_path=None):
        from src.config.settings import MailConfig
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
        self.assertIn("testmail.app:ns:uuid-key", result)
        self.assertIn("mailslurp.com:sk_abc", result)

    def test_providers_for_fallback_when_db_empty(self):
        from unittest.mock import patch
        mail = self._mail()
        with patch("src.core.database.get_mail_providers", return_value=[]):
            result = mail.providers_for()
        self.assertEqual(result, ())

    def test_providers_for_raises_on_db_error(self):
        from unittest.mock import patch
        mail = self._mail()
        with patch("src.core.database.get_mail_providers", side_effect=Exception("DB error")):
            with self.assertRaises(Exception):
                mail.providers_for()

    def test_all_providers_uses_providers_for(self):
        from unittest.mock import patch
        mail = self._mail()
        mock_rows = [{"connection_str": "mailslurp.com:sk_key"}]
        with patch("src.core.database.get_mail_providers", return_value=mock_rows):
            self.assertEqual(mail.all_providers, ("mailslurp.com:sk_key",))

    def test_providers_for_service_tag_passed_to_db(self):
        from unittest.mock import patch
        mail = self._mail()
        with patch("src.core.database.get_mail_providers", return_value=[]) as mock_db:
            mail.providers_for("chatgpt")
        _args, kwargs = mock_db.call_args
        self.assertEqual(kwargs.get("service_tag"), "chatgpt")

    def test_providers_for_case_insensitive(self):
        from unittest.mock import patch
        mail = self._mail()
        with patch("src.core.database.get_mail_providers", return_value=[]) as mock_db:
            mail.providers_for("ChatGPT")
        _args, kwargs = mock_db.call_args
        self.assertEqual(kwargs.get("service_tag"), "chatgpt")

    def test_providers_for_no_service_passes_none(self):
        from unittest.mock import patch
        mail = self._mail()
        with patch("src.core.database.get_mail_providers", return_value=[]) as mock_db:
            mail.providers_for()
        _args, kwargs = mock_db.call_args
        self.assertIsNone(kwargs.get("service_tag"))


class TestLoadRaw(unittest.TestCase):
    def test_merges_multiple_yaml_files(self):
        import tempfile
        from pathlib import Path
        from src.config.settings import _load_raw

        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp) / "config"
            cfg_dir.mkdir()
            (cfg_dir / "config.yaml").write_text("browser:\n  headless: true\n", encoding="utf-8")
            (cfg_dir / "logging.yaml").write_text("log:\n  append: false\n", encoding="utf-8")
            raw = _load_raw(Path(tmp))

        self.assertTrue(raw["browser"]["headless"])
        self.assertFalse(raw["log"]["append"])

    def test_later_file_overrides_earlier(self):
        import tempfile
        from pathlib import Path
        from src.config.settings import _load_raw

        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp) / "config"
            cfg_dir.mkdir()
            (cfg_dir / "config.yaml").write_text("browser:\n  headless: true\n", encoding="utf-8")
            (cfg_dir / "logging.yaml").write_text("browser:\n  headless: false\n", encoding="utf-8")
            raw = _load_raw(Path(tmp))

        self.assertFalse(raw["browser"]["headless"])

    def test_returns_empty_dict_when_no_config_folder(self):
        import tempfile
        from pathlib import Path
        from src.config.settings import _load_raw

        with tempfile.TemporaryDirectory() as tmp:
            raw = _load_raw(Path(tmp))

        self.assertEqual(raw, {})

    def test_ignores_missing_files_in_sequence(self):
        import tempfile
        from pathlib import Path
        from src.config.settings import _load_raw

        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp) / "config"
            cfg_dir.mkdir()
            # Chá»‰ táº¡o mail.yaml, bá» qua cÃ¡c file khÃ¡c
            (cfg_dir / "mail.yaml").write_text("mail:\n  cooldown_sec: 60\n", encoding="utf-8")
            raw = _load_raw(Path(tmp))

        self.assertEqual(raw.get("mail", {}).get("cooldown_sec"), 60)


class TestLoadConfigNew(unittest.TestCase):
    def _write_config(self, tmp, yaml_text):
        from pathlib import Path
        cfg_dir = Path(tmp) / "config"
        cfg_dir.mkdir(exist_ok=True)
        (cfg_dir / "config.yaml").write_text(yaml_text, encoding="utf-8")
        return cfg_dir

    def test_loads_browser_and_timeouts(self):
        import tempfile
        from src.config.settings import load_config

        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = self._write_config(tmp, "browser:\n  headless: true\ntimeouts:\n  email_wait: 45\n")
            cfg = load_config(cfg_dir / "config.yaml")

        self.assertTrue(cfg.headless)
        self.assertEqual(cfg.timeouts.email_wait, 45)

    def test_mail_cooldown_parsed(self):
        import tempfile
        from src.config.settings import load_config

        yaml_text = "mail:\n  cooldown_sec: 90\n  max_consecutive_fails: 5\n"
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = self._write_config(tmp, yaml_text)
            cfg = load_config(cfg_dir / "config.yaml")

        self.assertEqual(cfg.mail.cooldown_sec, 90)
        self.assertEqual(cfg.mail.max_consecutive_fails, 5)

    def test_openrouter_config_loaded(self):
        import tempfile
        from src.config.settings import load_config

        yaml_text = (
            "openrouter:\n"
            "  signup_url: https://openrouter.ai/sign-up\n"
            "  turnstile_sitekey: custom-sitekey\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = self._write_config(tmp, yaml_text)
            cfg = load_config(cfg_dir / "config.yaml")

        self.assertEqual(cfg.openrouter.signup_url, "https://openrouter.ai/sign-up")
        self.assertEqual(cfg.openrouter.turnstile_sitekey, "custom-sitekey")

    def test_openrouter_defaults_when_not_configured(self):
        import tempfile
        from pathlib import Path
        from src.config.settings import load_config

        with tempfile.TemporaryDirectory() as tmp:
            cfg = load_config(Path(tmp) / "config" / "config.yaml")

        self.assertEqual(cfg.openrouter.signup_url, "https://openrouter.ai/sign-up")
        self.assertTrue(cfg.openrouter.turnstile_sitekey)

    def test_returns_defaults_on_empty_dir(self):
        import tempfile
        from pathlib import Path
        from src.config.settings import load_config

        with tempfile.TemporaryDirectory() as tmp:
            cfg = load_config(Path(tmp) / "config" / "config.yaml")

        self.assertFalse(cfg.log.append)
        self.assertEqual(cfg.timeouts.email_wait, 120)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# src/services/chatgpt_com/page_actions.py
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestFillBirthday(unittest.TestCase):
    def _run_and_get_date(self):
        import re, asyncio
        from src.services.chatgpt_com.page_actions import fill_birthday
        from unittest.mock import AsyncMock

        page = MagicMock()
        loc = MagicMock()
        loc.count = AsyncMock(return_value=0)
        loc.first.is_visible = AsyncMock(return_value=False)
        page.locator.return_value = loc

        captured: list[str] = []
        with patch("src.services.chatgpt_com.page_actions.try_continue", new_callable=AsyncMock):
            asyncio.run(fill_birthday(page, captured.append))

        logged = str(captured)
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", logged)
        self.assertIsNotNone(m, f"fill_birthday did not log an ISO date: {logged}")
        return int(m.group(1)), int(m.group(2)), int(m.group(3))

    def test_year_in_range(self):
        year, _, _ = self._run_and_get_date()
        self.assertGreaterEqual(year, 1975)
        self.assertLessEqual(year, 1998)

    def test_month_in_range(self):
        _, month, _ = self._run_and_get_date()
        self.assertGreaterEqual(month, 1)
        self.assertLessEqual(month, 12)

    def test_day_in_range(self):
        _, _, day = self._run_and_get_date()
        self.assertGreaterEqual(day, 1)
        self.assertLessEqual(day, 28)

    def test_birthday_varies_across_calls(self):
        import re, asyncio
        from src.services.chatgpt_com.page_actions import fill_birthday
        from unittest.mock import AsyncMock

        dates = set()
        for _ in range(30):
            page = MagicMock()
            loc = MagicMock()
            loc.count = AsyncMock(return_value=0)
            loc.first.is_visible = AsyncMock(return_value=False)
            page.locator.return_value = loc
            captured: list[str] = []
            with patch("src.services.chatgpt_com.page_actions.try_continue", new_callable=AsyncMock):
                asyncio.run(fill_birthday(page, captured.append))
            m = re.search(r"(\d{4}-\d{2}-\d{2})", str(captured))
            if m:
                dates.add(m.group(1))

        self.assertGreater(len(dates), 1, "Birthday phai random qua nhieu lan goi")


class TestPageUtils(unittest.TestCase):
    def test_safe_load_calls_wait_for_load_state(self):
        import asyncio
        from src.core.page_utils import safe_load
        from unittest.mock import AsyncMock

        page = AsyncMock()
        asyncio.run(safe_load(page, timeout=5_000))
        page.wait_for_load_state.assert_called_once_with("domcontentloaded", timeout=5_000)

    def test_safe_load_silently_ignores_exception(self):
        import asyncio
        from src.core.page_utils import safe_load
        from unittest.mock import AsyncMock

        page = AsyncMock()
        page.wait_for_load_state.side_effect = TimeoutError("Navigation timeout")
        # Khong duoc raise
        asyncio.run(safe_load(page, timeout=5_000))

    def test_safe_load_passes_timeout_correctly(self):
        import asyncio
        from src.core.page_utils import safe_load
        from unittest.mock import AsyncMock

        page = AsyncMock()
        asyncio.run(safe_load(page, timeout=30_000))
        _, kwargs = page.wait_for_load_state.call_args
        self.assertEqual(kwargs.get("timeout") or page.wait_for_load_state.call_args[0][1], 30_000)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# src/checkers/chatgpt.py
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestCheckAccountSignature(unittest.TestCase):
    def test_refresh_token_has_client_id_param(self):
        import inspect
        from src.checkers.chatgpt import refresh_token

        sig = inspect.signature(refresh_token)
        self.assertIn("client_id", sig.parameters)

    def test_check_account_has_client_id_param(self):
        import inspect
        from src.checkers.chatgpt import check_account

        sig = inspect.signature(check_account)
        self.assertIn("client_id", sig.parameters)

    def test_check_account_confirmed_has_client_id_param(self):
        import inspect
        from src.checkers.chatgpt import check_account_confirmed

        sig = inspect.signature(check_account_confirmed)
        self.assertIn("client_id", sig.parameters)

    @patch("src.checkers.chatgpt.refresh_token", new_callable=AsyncMock)
    def test_check_account_passes_client_id_to_refresh_token(self, mock_refresh):
        import asyncio
        from src.checkers.chatgpt import check_account

        mock_refresh.return_value = None  # token refresh fails -> early exit
        account = {
            "email": "user@example.com",
            "password": "pw",
            "refresh_token": "rt-abc",
            "disabled": False,
        }
        result = asyncio.run(check_account(account, client_id="custom-client-id"))

        mock_refresh.assert_called_once_with("rt-abc", "custom-client-id", None)
        self.assertFalse(result["valid"])

    @patch("src.checkers.chatgpt.refresh_token", new_callable=AsyncMock)
    def test_check_account_uses_refreshed_access_token(self, mock_refresh):
        import asyncio
        from src.checkers.chatgpt import check_account

        mock_refresh.return_value = {
            "access_token": "new-at",
            "refresh_token": "new-rt",
            "id_token": "new-id",
            "account_id": "acc-123",
            "expired": "2099-01-01T00:00:00+00:00",
            "last_refresh": "2025-01-01T00:00:00+00:00",
        }
        me_resp = MagicMock()
        me_resp.status_code = 200
        me_resp.json.return_value = {"name": "Test", "id": "uid-1", "orgs": {"data": []}}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=me_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        account = {"email": "u@e.com", "password": "pw", "refresh_token": "rt-old"}
        with patch("src.checkers.chatgpt.httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(check_account(account, client_id="client-xyz"))

        self.assertTrue(result["valid"])
        headers_used = mock_client.get.call_args[1]["headers"]
        self.assertIn("new-at", headers_used.get("Authorization", ""))

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# src/api/services/registration_service.py
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestJobDataclass(unittest.TestCase):
    def _svc(self):
        # Isolate module-level _store between tests by importing fresh each test
        from src.api.services import registration_service as rs
        return rs

    def test_create_job_returns_pending(self):
        rs = self._svc()
        j = rs.create_job("ELEVENLABS", 3)
        self.assertEqual(j.status, "pending")
        self.assertEqual(j.service, "ELEVENLABS")
        self.assertEqual(j.count, 3)

    def test_create_job_clamps_workers(self):
        rs = self._svc()
        j = rs.create_job("CHATGPT", 1, workers=99)
        self.assertEqual(j.workers, 10)

    def test_create_job_workers_minimum_one(self):
        rs = self._svc()
        j = rs.create_job("CHATGPT", 1, workers=0)
        self.assertEqual(j.workers, 1)

    def test_get_job_returns_stored_job(self):
        rs = self._svc()
        j = rs.create_job("OPENROUTER", 2)
        self.assertIs(rs.get_job(j.id), j)

    def test_get_job_unknown_id_returns_none(self):
        rs = self._svc()
        self.assertIsNone(rs.get_job("does-not-exist"))

    def test_list_jobs_includes_created_job(self):
        rs = self._svc()
        j = rs.create_job("PROTON", 1)
        self.assertIn(j, rs.list_jobs())

    def test_cancel_job_sets_flag(self):
        rs = self._svc()
        j = rs.create_job("LEONARDO", 2)
        j.status = "running"
        result = rs.cancel_job(j.id)
        self.assertTrue(result)

    def test_cancel_done_job_returns_false(self):
        rs = self._svc()
        j = rs.create_job("LEONARDO", 1)
        j.status = "done"
        self.assertFalse(rs.cancel_job(j.id))

    def test_cancel_unknown_id_returns_false(self):
        rs = self._svc()
        self.assertFalse(rs.cancel_job("no-such-id"))

    def test_job_has_iso_created_at(self):
        rs = self._svc()
        j = rs.create_job("CHATGPT", 1)
        self.assertRegex(j.created_at, r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")


class TestMakeStreamLogFn(unittest.TestCase):
    def test_log_fn_calls_file_logger(self):
        import asyncio
        from src.api.services.registration_service import make_stream_log_fn
        from src.api.ws.log_manager import LogBus
        from unittest.mock import AsyncMock

        bus = LogBus()
        file_logger = MagicMock()
        log_fn = make_stream_log_fn(bus, "job-abc", file_logger)

        with patch("asyncio.ensure_future"), \
             patch("src.api.services.registration_service.broadcast"):
            log_fn("hello")
            log_fn("world")

        self.assertEqual(file_logger.logger.info.call_count, 2)
        calls = [str(c) for c in file_logger.logger.info.call_args_list]
        self.assertTrue(any("hello" in c for c in calls))
        self.assertTrue(any("world" in c for c in calls))


class TestRunWorkerMocked(unittest.TestCase):
    """_run_worker vá»›i mock registrar â€” khÃ´ng má»Ÿ browser."""

    def _job(self, count=2, workers=1):
        from src.api.services.registration_service import Job
        import uuid
        return Job(id=str(uuid.uuid4()), service="ELEVENLABS", count=count, workers=workers)

    def _run(self, job, registrar_result=True, registrar_exc=None):
        import asyncio
        from src.api.services import registration_service as rs

        logs: list[str] = []
        saves: list = []

        def log_fn(msg): logs.append(msg)
        def save_fn(rec): saves.append(rec)

        # Patch make_registrar Ä‘á»ƒ tráº£ mock registrar function
        def fake_make_registrar(service, cfg, shared_callback_server=None):
            async def registrar(*, log_fn, save_fn):
                if registrar_exc:
                    raise registrar_exc
                return registrar_result
            return registrar

        with patch("src.services.registry.make_registrar", fake_make_registrar), \
             patch("src.api.services.registration_service.load_config") as mock_load:
            mock_load.return_value.registration.max_consecutive_fails = 3
            asyncio.run(rs._run_worker(job, log_fn, save_fn))

        return job, logs

    def test_success_sets_done_status(self):
        job = self._job(count=2)
        job, logs = self._run(job, registrar_result=True)
        self.assertEqual(job.status, "done")
        self.assertEqual(job.created_count, 2)

    def test_all_fail_sets_failed_status(self):
        job = self._job(count=2)
        job, logs = self._run(job, registrar_result=False)
        self.assertEqual(job.status, "failed")
        self.assertEqual(job.created_count, 0)

    def test_registrar_exception_does_not_abort_other_workers(self):
        import asyncio
        """Má»™t exception khÃ´ng kill pool cáº£ job."""
        job = self._job(count=1, workers=1)
        calls = [0]
        logs: list[str] = []

        def log_fn(msg): logs.append(msg)
        def save_fn(rec): pass

        def fake_make_registrar(service, cfg, shared_callback_server=None):
            async def registrar(*, log_fn, save_fn):
                calls[0] += 1
                if calls[0] == 1:
                    raise RuntimeError("browser crash")
                return True
            return registrar

        from src.api.services import registration_service as rs
        with patch("src.services.registry.make_registrar", fake_make_registrar), \
             patch("src.api.services.registration_service.load_config") as mock_load2:
            mock_load2.return_value.registration.max_consecutive_fails = 3
            asyncio.run(rs._run_worker(job, log_fn, save_fn))

        # count=1: first attempt fails, second succeeds -> done with 1 created
        self.assertEqual(job.created_count, 1)
        self.assertEqual(job.status, "done")

    def test_unknown_service_sets_failed(self):
        import asyncio
        from src.api.services import registration_service as rs
        from src.api.services.registration_service import Job
        import uuid

        job = Job(id=str(uuid.uuid4()), service="NONEXISTENT_XYZ", count=1)
        logs: list[str] = []

        def log_fn(msg): logs.append(msg)

        with patch("src.api.services.registration_service.load_config"), \
             patch("src.services.registry.make_registrar", return_value=None):
            asyncio.run(rs._run_worker(job, log_fn, lambda r: None))

        self.assertEqual(job.status, "failed")
        self.assertIn("Unknown service", job.error)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# src/core/database.py
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestDatabaseCRUD(unittest.TestCase):
    def _db(self, tmp):
        from pathlib import Path
        from src.core.database import init_db
        db = Path(tmp) / "test.db"
        init_db(db)
        return db

    def _cleanup_engine(self, db_path):
        """Dispose SQLAlchemy engine vÃ  xÃ³a khá»i cache â€” trÃ¡nh WinError 32."""
        from src.core.database import _engines
        key = str(db_path.resolve())
        engine = _engines.pop(key, None)
        if engine:
            engine.dispose()

    def _record(self, email="a@b.com", service="ELEVENLABS"):
        from src.core.storage import AccountRecord
        return AccountRecord(service=service, email=email, password="pw", api_key="sk_test")

    def test_insert_and_get(self):
        import tempfile
        from src.core.database import insert_account, get_account_by_email

        with tempfile.TemporaryDirectory() as tmp:
            db = self._db(tmp)
            try:
                insert_account(db, self._record())
                acc = get_account_by_email(db, "ELEVENLABS", "a@b.com")
                self.assertIsNotNone(acc)
                self.assertEqual(acc["email"], "a@b.com")
                self.assertEqual(acc["api_key"], "sk_test")
            finally:
                self._cleanup_engine(db)

    def test_get_accounts_filtered_by_service(self):
        import tempfile
        from src.core.database import insert_account, get_accounts

        with tempfile.TemporaryDirectory() as tmp:
            db = self._db(tmp)
            try:
                insert_account(db, self._record("a@a.com", "ELEVENLABS"))
                insert_account(db, self._record("b@b.com", "OPENROUTER"))
                only_el = get_accounts(db, "ELEVENLABS")
                all_accs = get_accounts(db)
                self.assertEqual(len(only_el), 1)
                self.assertEqual(only_el[0]["email"], "a@a.com")
                self.assertEqual(len(all_accs), 2)
            finally:
                self._cleanup_engine(db)

    def test_update_account(self):
        import tempfile
        from src.core.database import insert_account, update_account, get_account_by_email

        with tempfile.TemporaryDirectory() as tmp:
            db = self._db(tmp)
            try:
                insert_account(db, self._record())
                ok = update_account(db, "ELEVENLABS", "a@b.com", disabled=True)
                self.assertTrue(ok)
                acc = get_account_by_email(db, "ELEVENLABS", "a@b.com")
                self.assertTrue(acc["disabled"])
            finally:
                self._cleanup_engine(db)

    def test_delete_account(self):
        import tempfile
        from src.core.database import insert_account, delete_account, get_account_by_email

        with tempfile.TemporaryDirectory() as tmp:
            db = self._db(tmp)
            try:
                insert_account(db, self._record())
                ok = delete_account(db, "ELEVENLABS", "a@b.com")
                self.assertTrue(ok)
                self.assertIsNone(get_account_by_email(db, "ELEVENLABS", "a@b.com"))
            finally:
                self._cleanup_engine(db)

    def test_delete_nonexistent_returns_false(self):
        import tempfile
        from src.core.database import delete_account

        with tempfile.TemporaryDirectory() as tmp:
            db = self._db(tmp)
            try:
                self.assertFalse(delete_account(db, "ELEVENLABS", "noone@nowhere.com"))
            finally:
                self._cleanup_engine(db)

    def test_update_nonexistent_returns_false(self):
        import tempfile
        from src.core.database import update_account

        with tempfile.TemporaryDirectory() as tmp:
            db = self._db(tmp)
            try:
                self.assertFalse(update_account(db, "ELEVENLABS", "ghost@x.com", disabled=True))
            finally:
                self._cleanup_engine(db)

    def test_upsert_updates_existing(self):
        import tempfile
        from src.core.database import insert_account, upsert_account, get_account_by_email
        from src.core.storage import AccountRecord

        with tempfile.TemporaryDirectory() as tmp:
            db = self._db(tmp)
            try:
                insert_account(db, AccountRecord(service="OPENROUTER", email="u@e.com", password="pw"))
                upsert_account(db, AccountRecord(service="OPENROUTER", email="u@e.com", password="pw", api_key="sk_new"))
                acc = get_account_by_email(db, "OPENROUTER", "u@e.com")
                self.assertEqual(acc["api_key"], "sk_new")
            finally:
                self._cleanup_engine(db)

    def test_count_accounts(self):
        import tempfile
        from src.core.database import insert_account, count_accounts

        with tempfile.TemporaryDirectory() as tmp:
            db = self._db(tmp)
            try:
                insert_account(db, self._record("x@x.com", "ELEVENLABS"))
                insert_account(db, self._record("y@y.com", "ELEVENLABS"))
                self.assertEqual(count_accounts(db, "ELEVENLABS"), 2)
            finally:
                self._cleanup_engine(db)

    def test_bulk_insert(self):
        import tempfile
        from src.core.database import bulk_insert, get_accounts
        from src.core.storage import AccountRecord

        records = [
            AccountRecord(service="CHATGPT", email=f"u{i}@x.com", password="pw")
            for i in range(5)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            db = self._db(tmp)
            try:
                n = bulk_insert(db, records)
                self.assertEqual(n, 5)
                self.assertEqual(len(get_accounts(db, "CHATGPT")), 5)
            finally:
                self._cleanup_engine(db)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# src/services/registry.py
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestRegistry(unittest.TestCase):
    def test_supported_services_non_empty(self):
        from src.services.registry import SUPPORTED_SERVICES
        self.assertGreater(len(SUPPORTED_SERVICES), 0)

    def test_make_registrar_known_service_returns_callable(self):
        from src.services.registry import make_registrar, SUPPORTED_SERVICES
        from src.config.settings import AppConfig
        cfg = AppConfig()
        for svc in SUPPORTED_SERVICES:
            with self.subTest(service=svc):
                r = make_registrar(svc, cfg)
                self.assertTrue(callable(r))

    def test_make_registrar_unknown_returns_none(self):
        from src.services.registry import make_registrar
        from src.config.settings import AppConfig
        self.assertIsNone(make_registrar("DOES_NOT_EXIST", AppConfig()))


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# src/services/testmail_app/registrar.py â€” smoke + pure helpers
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestTestmailRegistrar(unittest.TestCase):
    """Smoke tests: import ok + táº¥t cáº£ cfg.* attribute access khÃ´ng raise."""

    def test_import_ok(self):
        from src.services.testmail_app import registrar  # noqa: F401

    def test_config_attrs_accessible(self):
        """Catch AttributeError khi dÃ¹ng sai config field (vd: cfg.timeouts.otp_wait_sec)."""
        from src.config.settings import AppConfig
        from src.services.testmail_app import registrar as m  # noqa: F401
        cfg = AppConfig()
        _ = cfg.timeouts.email_wait
        _ = cfg.base_dir
        _ = cfg.headless

    def test_random_name_returns_valid_tuple(self):
        from src.services.testmail_app.registrar import _random_name
        first, last = _random_name()
        self.assertIn(first, ["Alex", "Jordan", "Casey", "Riley", "Morgan", "Taylor", "Quinn", "Avery"])
        self.assertTrue(last[0].isupper())
        self.assertGreater(len(last), 1)

    def test_extract_verification_code_dashes(self):
        from src.services.testmail_app.registrar import _extract_verification_code
        body = "some text\n----------\nABCD1234\n----------\nmore text"
        self.assertEqual(_extract_verification_code(body), "ABCD1234")

    def test_extract_verification_code_none_when_missing(self):
        from src.services.testmail_app.registrar import _extract_verification_code
        self.assertIsNone(_extract_verification_code("nothing useful here"))

    def test_extract_uuid_api_key(self):
        from src.services.testmail_app.registrar import _extract_uuid_api_key
        # New format: apikey= query param in URL
        text = "https://client.testmail.app/docs/json-api?apikey=6c810403-1e7a-4f96-ac8a-03f43616c605&namespace=im4vw"
        self.assertEqual(_extract_uuid_api_key(text), "6c810403-1e7a-4f96-ac8a-03f43616c605")

    def test_extract_uuid_api_key_none_when_missing(self):
        from src.services.testmail_app.registrar import _extract_uuid_api_key
        self.assertIsNone(_extract_uuid_api_key("no uuid here"))

    def test_extract_namespace(self):
        from src.services.testmail_app.registrar import _extract_namespace
        self.assertEqual(_extract_namespace('"namespace": "im4vw"'), "im4vw")   # JSON with quotes
        self.assertEqual(_extract_namespace('"namespace":"im4vw"'), "im4vw")    # JSON no space
        self.assertEqual(_extract_namespace('"namespace": im4vw'), "im4vw")     # unquoted value

    def test_extract_namespace_none_when_missing(self):
        from src.services.testmail_app.registrar import _extract_namespace
        self.assertIsNone(_extract_namespace("no namespace here"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
