"""
gmail_inbox_service.py — Service layer giữa Router và mail provider.

Trách nhiệm duy nhất: load Mailbox từ DB + ủy thác cho gmail provider.
Router không biết gì về Camoufox, storage_state, hay DB schema.

Tất cả public functions đều pure async, không có side-effect ngoài provider calls.
"""
from __future__ import annotations

import asyncio
import re

from common.database import get_mailbox_record
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

async def load_inbox_mailbox(db_path, email: str):
    """
    Load Mailbox object từ DB theo email.
    Raise MailboxNotFoundError nếu không tìm thấy.
    Raise SessionExpiredError nếu chưa có google_auth_state.
    """
    record = await asyncio.to_thread(get_mailbox_record, db_path, email)
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

async def list_inbox(db_path, email: str, unread_only: bool) -> list[GmailMessage]:
    box = await load_inbox_mailbox(db_path, email)
    return await get_messages(box, unread_only=unread_only)


async def search_inbox(db_path, email: str, query: str) -> list[GmailMessage]:
    box = await load_inbox_mailbox(db_path, email)
    return await search_messages(box, query)


async def fetch_body(db_path, email: str, message_id: str) -> str:
    box = await load_inbox_mailbox(db_path, email)
    return await get_message_body(box, message_id)


async def extract_otp(db_path, email: str, message_id: str, digits: int) -> dict:
    """
    Fetch email body và extract OTP code có đúng `digits` chữ số.
    Raise ValueError nếu không tìm thấy OTP.
    """
    body = await fetch_body(db_path, email, message_id)
    plain = re.sub(r"<[^>]+>", " ", body)
    pattern = rf"(?<!\d)(\d{{{digits}}})(?!\d)"
    matches = re.findall(pattern, plain)
    if not matches:
        raise ValueError(
            f"Khong tim thay OTP {digits} chu so trong email {message_id!r}"
        )
    return {"otp": matches[0], "all_matches": matches, "digits": digits}


async def poll_for_message(
    db_path,
    email: str,
    from_contains: str,
    subject_contains: str,
    timeout: int,
    poll_interval: int,
) -> GmailMessage | None:
    box = await load_inbox_mailbox(db_path, email)
    return await wait_for_message(
        box,
        from_contains=from_contains,
        subject_contains=subject_contains,
        timeout=timeout,
        poll_interval=poll_interval,
    )
