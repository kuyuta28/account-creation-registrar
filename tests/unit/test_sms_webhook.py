"""
unit/test_sms_webhook.py — Tests cho SMS webhook provider + client dispatch.

Bao phủ:
  - sms_webhook.py: push_sms, make_mailbox, get_messages, wait_for_message, _matches
  - client.py: _create_mailbox_on_provider với sms.webhook format
  - client.py: wait_for_message dispatch cho sms.webhook provider
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fresh_store():
    """Clear global SMS store giữa tests."""
    from src.mail.providers import sms_webhook
    sms_webhook._SMS_STORE.clear()
    sms_webhook._SMS_EVENTS.clear()


# ── sms_webhook: make_mailbox ─────────────────────────────────────────────────

class TestMakeMailbox:
    def test_provider_is_sms_webhook(self):
        from src.mail.providers.sms_webhook import make_mailbox
        box = make_mailbox("+84912345678")
        assert box.provider == "sms.webhook"

    def test_phone_normalized(self):
        from src.mail.providers.sms_webhook import make_mailbox
        box = make_mailbox("+84 912-345-678")
        assert box.email == "84912345678"

    def test_phone_without_plus(self):
        from src.mail.providers.sms_webhook import make_mailbox
        box = make_mailbox("84912345678")
        assert box.email == "84912345678"


# ── sms_webhook: push_sms + get_messages ──────────────────────────────────────

class TestPushAndGetMessages:
    def setup_method(self):
        _fresh_store()

    def test_push_then_get(self):
        from src.mail.providers.sms_webhook import get_messages, make_mailbox, push_sms
        push_sms("84912345678", from_="OTP_SERVICE", text="Your OTP is 123456", sent_stamp=0)
        box = make_mailbox("84912345678")
        msgs = get_messages(box)
        assert len(msgs) == 1
        assert msgs[0]["text"] == "Your OTP is 123456"
        assert msgs[0]["from_"] == "OTP_SERVICE"

    def test_get_messages_newest_first(self):
        from src.mail.providers.sms_webhook import get_messages, make_mailbox, push_sms
        push_sms("84912345678", from_="A", text="first", sent_stamp=1000)
        push_sms("84912345678", from_="B", text="second", sent_stamp=2000)
        box = make_mailbox("84912345678")
        msgs = get_messages(box)
        assert msgs[0]["text"] == "second"  # newest first
        assert msgs[1]["text"] == "first"

    def test_push_different_phones_isolated(self):
        from src.mail.providers.sms_webhook import get_messages, make_mailbox, push_sms
        push_sms("111", from_="X", text="for 111")
        push_sms("222", from_="Y", text="for 222")
        assert len(get_messages(make_mailbox("111"))) == 1
        assert len(get_messages(make_mailbox("222"))) == 1
        assert get_messages(make_mailbox("111"))[0]["text"] == "for 111"

    def test_store_cap_trims_oldest(self):
        from src.mail.providers import sms_webhook
        from src.mail.providers.sms_webhook import get_messages, make_mailbox, push_sms
        cap = sms_webhook._STORE_CAP
        for i in range(cap + 10):
            push_sms("999", from_="X", text=f"msg {i}")
        msgs = get_messages(make_mailbox("999"))
        assert len(msgs) <= cap

    def test_message_has_required_fields(self):
        from src.mail.providers.sms_webhook import get_messages, make_mailbox, push_sms
        push_sms("84912345678", from_="SENDER", text="hello", sent_stamp=9999)
        msgs = get_messages(make_mailbox("84912345678"))
        msg = msgs[0]
        assert "id" in msg
        assert "from_" in msg
        assert "text" in msg
        assert "sent_stamp" in msg


# ── sms_webhook: _matches ─────────────────────────────────────────────────────

class TestMatches:
    def test_empty_filters_match_all(self):
        from src.mail.providers.sms_webhook import _matches
        msg = {"from_": "ANYONE", "text": "anything"}
        assert _matches(msg, "", "") is True

    def test_from_filter_case_insensitive(self):
        from src.mail.providers.sms_webhook import _matches
        msg = {"from_": "OTP_SERVICE", "text": "code: 123456"}
        assert _matches(msg, "otp_service", "") is True
        assert _matches(msg, "OTP", "") is True
        assert _matches(msg, "OTHER", "") is False

    def test_body_filter_case_insensitive(self):
        from src.mail.providers.sms_webhook import _matches
        msg = {"from_": "X", "text": "Your OTP is 654321"}
        assert _matches(msg, "", "otp") is True
        assert _matches(msg, "", "654321") is True
        assert _matches(msg, "", "wrong") is False

    def test_both_filters_must_match(self):
        from src.mail.providers.sms_webhook import _matches
        msg = {"from_": "OLLAMA", "text": "code: 999999"}
        assert _matches(msg, "OLLAMA", "999999") is True
        assert _matches(msg, "OLLAMA", "wrong") is False
        assert _matches(msg, "wrong", "999999") is False


# ── sms_webhook: wait_for_message ─────────────────────────────────────────────

class TestWaitForMessage:
    def setup_method(self):
        _fresh_store()

    def test_returns_matching_msg_already_in_store(self):
        from src.mail.providers.sms_webhook import make_mailbox, push_sms, wait_for_message
        push_sms("84912345678", from_="OLLAMA", text="Your code is 112233")
        box = make_mailbox("84912345678")

        result = asyncio.run(wait_for_message(box, from_contains="ollama", timeout=5))
        assert result is not None
        assert "112233" in result["text"]

    def test_returns_none_on_timeout(self):
        from src.mail.providers.sms_webhook import make_mailbox, wait_for_message
        box = make_mailbox("84900000000")
        result = asyncio.run(wait_for_message(box, from_contains="ollama", timeout=2, poll_interval=1.0))
        assert result is None

    def test_wakes_up_on_push_during_wait(self):
        from src.mail.providers.sms_webhook import make_mailbox, push_sms, wait_for_message

        box = make_mailbox("84911111111")

        async def _scenario():
            async def _push_later():
                await asyncio.sleep(0.3)
                push_sms("84911111111", from_="SERVICE", text="OTP: 777888")

            waiter = asyncio.create_task(wait_for_message(box, from_contains="service", timeout=5))
            asyncio.create_task(_push_later())
            return await waiter

        result = asyncio.run(_scenario())
        assert result is not None
        assert "777888" in result["text"]

    def test_body_contains_filter(self):
        from src.mail.providers.sms_webhook import make_mailbox, push_sms, wait_for_message
        push_sms("84922222222", from_="X", text="Token: ABCDEF")
        box = make_mailbox("84922222222")
        result = asyncio.run(wait_for_message(box, body_contains="abcdef", timeout=3))
        assert result is not None

    def test_no_match_on_wrong_filter(self):
        from src.mail.providers.sms_webhook import make_mailbox, push_sms, wait_for_message
        push_sms("84933333333", from_="OTHER", text="not relevant")
        box = make_mailbox("84933333333")
        result = asyncio.run(wait_for_message(box, from_contains="ollama", timeout=2, poll_interval=1.0))
        assert result is None


# ── client.py: _create_mailbox_on_provider sms.webhook format ────────────────

class TestClientSmsWebhookCreate:
    def test_valid_format_creates_mailbox(self):
        from src.mail.client import _create_mailbox_on_provider
        result = asyncio.run(_create_mailbox_on_provider("sms.webhook:84912345678"))
        assert result.provider == "sms.webhook"
        assert result.email == "84912345678"

    def test_invalid_format_raises(self):
        from src.mail.client import _create_mailbox_on_provider
        with pytest.raises(ValueError, match="sms.webhook"):
            asyncio.run(_create_mailbox_on_provider("sms.webhook:"))

    def test_missing_phone_raises(self):
        from src.mail.client import _create_mailbox_on_provider
        with pytest.raises((ValueError, Exception)):
            asyncio.run(_create_mailbox_on_provider("sms.webhook"))


# ── client.py: wait_for_message dispatch cho sms.webhook ─────────────────────

class TestClientWaitForMessageSms:
    def setup_method(self):
        _fresh_store()

    def test_dispatch_to_sms_webhook(self):
        from src.mail.providers.sms_webhook import make_mailbox, push_sms
        from src.mail.client import wait_for_message

        push_sms("84999000111", from_="OLLAMA_COM", text="Verify: 445566")
        box = make_mailbox("84999000111")

        result = asyncio.run(wait_for_message(box, from_contains="ollama", timeout=5))
        assert result is not None
        assert "445566" in result["text"]
