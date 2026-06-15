"""
gmail_inbox_service.py — Service layer giữa Router và mail provider.

Trách nhiệm duy nhất: load Mailbox từ DB + ủy thác cho gmail provider.
Router không biết gì về Camoufox, storage_state, hay DB schema.

Tất cả public functions đều pure async, không có side-effect ngoài provider calls.
"""
from __future__ import annotations

import re

from common.database._async import get_mailbox_record_async
from common.database._engine import get_async_session
from ...mail.providers.gmail import (
    GmailMessage,
    get_message_body,
    get_messages,
    make_mailbox,
    search_messages,
    wait_for_message,
)


class MailboxNotFoundError(ValueError):
    pass


class SessionExpiredError(RuntimeError):
    pass


# ── Mailbox loader (pure function, không side-effect) ─────────────────────────

async def load_inbox_mailbox(email: str):
    """
    Load Mailbox object từ PostgreSQL theo email.
    Raise MailboxNotFoundError nếu không tìm thấy.
    Raise SessionExpiredError nếu chưa có google_auth_state.
    """
    async with get_async_session() as session:
        record = await get_mailbox_record_async(session, email)
    if not record:
        raise MailboxNotFoundError(email)
    google_auth_state = record.get("google_auth_state")
    if not google_auth_state:
        raise SessionExpiredError(email)
    return make_mailbox(
        email=record["email"],
        google_auth_state=google_auth_state,
        password=record.get("password", ""),
        totp_secret=record.get("totp_secret", ""),
    )


# ── Inbox operations ──────────────────────────────────────────────────────────

async def list_inbox(email: str, unread_only: bool) -> list[GmailMessage]:
    box = await load_inbox_mailbox(email)
    return await get_messages(box, unread_only=unread_only)


async def search_inbox(email: str, query: str) -> list[GmailMessage]:
    box = await load_inbox_mailbox(email)
    return await search_messages(box, query)


async def fetch_body(email: str, message_id: str) -> str:
    box = await load_inbox_mailbox(email)
    return await get_message_body(box, message_id)


async def extract_otp(email: str, message_id: str, digits: int) -> dict:
    """
    Fetch email body và extract OTP code có đúng `digits` chữ số.
    Raise ValueError nếu không tìm thấy OTP.
    """
    body = await fetch_body(email, message_id)
    plain = re.sub(r"<[^>]+>", " ", body)
    pattern = rf"(?<!\d)(\d{{{digits}}})(?!\d)"
    matches = re.findall(pattern, plain)
    if not matches:
        raise ValueError(
            f"Khong tim thay OTP {digits} chu so trong email {message_id!r}"
        )
    return {"otp": matches[0], "all_matches": matches, "digits": digits}


async def poll_for_message(
    email: str,
    from_contains: str,
    subject_contains: str,
    timeout: int,
    poll_interval: int,
) -> GmailMessage | None:
    box = await load_inbox_mailbox(email)
    return await wait_for_message(
        box,
        from_contains=from_contains,
        subject_contains=subject_contains,
        timeout=timeout,
        poll_interval=poll_interval,
    )
