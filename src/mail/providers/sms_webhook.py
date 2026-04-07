"""
mail/providers/sms_webhook.py — SMS provider via Android webhook (SmsForwarder, pppscn/SmsForwarder).

Provider string format: "sms.webhook:{phone_number}"
    phone_number = số điện thoại SIM nhận (dùng để match đúng hộp thư)

Architecture:
  Android App (SmsForwarder) → POST /api/v1/sms/webhook → push_sms() → asyncio.Queue
  Registrar gọi wait_for_message(box, ...) → poll queue → trả về SMS khớp

Public API:
  make_mailbox(phone_number)                            -> Mailbox
  push_sms(phone_number, from_, text, sent_stamp)       -> None   (gọi từ router)
  get_messages(box)                                     -> list[dict]
  wait_for_message(box, from_contains, body_contains,
                   timeout, poll_interval, log_fn)      -> dict | None
"""
from __future__ import annotations

import asyncio
import time
from typing import TypedDict

from .._base import LogFn, Mailbox, _tprint

_PROVIDER = "sms.webhook"

# ── In-memory SMS store per phone number ─────────────────────────────────────
# phone_number (normalized) → list[SmsMessage] (capped tại 500 entries)
_SMS_STORE:  dict[str, list[SmsMessage]] = {}
_SMS_EVENTS: dict[str, asyncio.Event] = {}       # wakeup event khi có SMS mới
_STORE_CAP = 500


class SmsMessage(TypedDict):
    id: str          # "{phone_number}:{from_}:{sent_stamp}"
    from_: str       # sender number/name
    text: str        # nội dung SMS
    sent_stamp: int  # epoch ms
    received_at: float  # time.monotonic()


def _normalize_phone(phone: str) -> str:
    return phone.strip().lstrip("+").replace(" ", "").replace("-", "")


# ── Mailbox factory ───────────────────────────────────────────────────────────

def make_mailbox(phone_number: str) -> Mailbox:
    """Tạo Mailbox đại diện cho 1 SIM card (số điện thoại nhận SMS)."""
    normalized = _normalize_phone(phone_number)
    return Mailbox(
        email=normalized,
        token="",
        account_id="",
        base_url="",
        provider=_PROVIDER,
    )


# ── Write path (gọi từ router) ───────────────────────────────────────────────

def push_sms(phone_number: str, from_: str, text: str, sent_stamp: int = 0) -> None:
    """
    Nhận SMS từ Android webhook, lưu vào store.
    Gọi từ FastAPI router — sync-safe (không cần await).
    """
    key = _normalize_phone(phone_number)
    if key not in _SMS_STORE:
        _SMS_STORE[key] = []

    msg: SmsMessage = {
        "id": f"{key}:{from_}:{sent_stamp or int(time.time() * 1000)}",
        "from_": from_.strip(),
        "text": text,
        "sent_stamp": sent_stamp or int(time.time() * 1000),
        "received_at": time.monotonic(),
    }

    store = _SMS_STORE[key]
    store.append(msg)
    if len(store) > _STORE_CAP:
        # Trim oldest
        _SMS_STORE[key] = store[-_STORE_CAP:]

    # Wake up any waiter
    event = _SMS_EVENTS.get(key)
    if event is not None:
        event.set()


# ── Read path ────────────────────────────────────────────────────────────────

def get_messages(box: Mailbox) -> list[dict]:
    """Trả toàn bộ SMS đã nhận cho phone_number này (newest-first)."""
    key = _normalize_phone(box.email)
    msgs = _SMS_STORE.get(key, [])
    return [_msg_to_dict(m) for m in reversed(msgs)]


async def wait_for_message(
    box: Mailbox,
    from_contains: str = "",
    body_contains: str = "",
    timeout: int = 120,
    poll_interval: float = 2.0,
    log_fn: LogFn | None = None,
    after_monotonic: float = 0.0,
) -> dict | None:
    """
    Đợi SMS mới khớp điều kiện.
    Trả về dict SMS đầu tiên khớp, hoặc None nếu timeout.

    Tham số:
        from_contains   — chuỗi con trong số gửi (case-insensitive). Rỗng = bất kỳ.
        body_contains   — chuỗi con trong nội dung SMS. Rỗng = bất kỳ.
        timeout         — giây tối đa chờ.
        poll_interval   — giây giữa các lần check (fallback khi event missed).
        after_monotonic — chỉ match SMS có received_at > giá trị này. Dùng để bỏ qua SMS cũ.
    """
    log = log_fn or _tprint
    key = _normalize_phone(box.email)

    # Tạo event nếu chưa có
    if key not in _SMS_EVENTS:
        _SMS_EVENTS[key] = asyncio.Event()

    event = _SMS_EVENTS[key]
    deadline = time.monotonic() + timeout
    seen_ids: set[str] = set()

    log(f"[sms] Waiting for SMS on {box.email} "
        f"(from_contains={from_contains!r}, body_contains={body_contains!r}, timeout={timeout}s)")

    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        event.clear()

        # Check current store
        msgs = _SMS_STORE.get(key, [])
        for msg in reversed(msgs):  # newest first
            if msg["id"] in seen_ids:
                continue
            if after_monotonic and msg["received_at"] <= after_monotonic:
                seen_ids.add(msg["id"])
                continue
            if _matches(msg, from_contains, body_contains):
                log(f"[sms] Matched SMS from={msg['from_']!r}: {msg['text'][:80]!r}")
                return _msg_to_dict(msg)
            seen_ids.add(msg["id"])

        # Wait for new SMS or timeout
        wait_sec = min(poll_interval, remaining)
        if wait_sec <= 0:
            break
        try:
            await asyncio.wait_for(asyncio.shield(event.wait()), timeout=wait_sec)
        except TimeoutError:
            pass

    log(f"[sms] Timeout after {timeout}s — no matching SMS received")
    return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _matches(msg: SmsMessage, from_contains: str, body_contains: str) -> bool:
    from_ok = (not from_contains) or (from_contains.lower() in msg["from_"].lower())
    body_ok = (not body_contains) or (body_contains.lower() in msg["text"].lower())
    return from_ok and body_ok


def _msg_to_dict(msg: SmsMessage) -> dict:
    return {
        "id": msg["id"],
        "from_": msg["from_"],
        "subject": f"SMS from {msg['from_']}",
        "text": msg["text"],
        "sent_stamp": msg["sent_stamp"],
        "unread": True,
    }
