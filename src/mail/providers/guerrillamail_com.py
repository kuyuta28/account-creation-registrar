"""
mail/providers/guerrillamail_com.py — Guerrilla Mail inbox provider.

Provider string format: "guerrillamail.com" (no API key needed)
Email format:           {random}@guerrillamail.com (or other domains like @sharklasers.com)
API:                    GET http://api.guerrillamail.com/ajax.php?f=...
Free tier:              FREE, no API key required, cookie-based sessions
Lifetime:               1 hour (extendable)
"""
from __future__ import annotations

import asyncio
import time

from .._base import LogFn, Mailbox, request_with_retry, _tprint

GUERRILLAMAIL_BASE = "https://www.guerrillamail.com/ajax.php"
GUERRILLAMAIL_PREFIX = "guerrillamail.com"

# Domains available from Guerrilla Mail
_GUERRILLA_DOMAINS = [
    "guerrillamail.com",
    "sharklasers.com",
    "guerrillamailblock.com",
    "pokemail.net",
    "spam4.me",
]


async def create_mailbox(provider: str, log_fn: LogFn | None = None) -> Mailbox:
    """Create a new Guerrilla Mail inbox (no API key needed)."""
    _log = log_fn or _tprint

    # Get email address - Guerrilla Mail creates session automatically
    response = await request_with_retry(
        "GET",
        GUERRILLAMAIL_BASE,
        params={
            "f": "get_email_address",
            "ip": "1.1.1.1",  # Dummy IP (required param)
            "agent": "Mozilla/5.0",  # Required user agent
            "lang": "en",
        },
        provider_name="guerrillamail.com",
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()

    # Response format: {"email_addr": "abc123@guerrillamail.com", "sid_token": "..."}
    email = data.get("email_addr", "")
    sid_token = data.get("sid_token", "")

    if not email:
        raise RuntimeError(f"Guerrilla Mail did not return email: {data}")

    # Extract email parts
    email_user, _, _email_domain = email.partition("@")

    _log(f"Guerrilla Mail: {email}")

    return Mailbox(
        email=email,
        token=sid_token,  # Store sid_token for session management
        account_id=email_user,  # Store email username
        base_url=GUERRILLAMAIL_BASE,
        provider="guerrillamail.com",
        api_key="",  # No API key needed
    )


async def get_messages(box: Mailbox) -> list[dict]:
    """Fetch all messages for a Guerrilla Mail inbox using check_email."""
    params = {
        "f": "check_email",  # Use check_email instead of get_email_list
        "seq": 1,  # Sequence number for new emails
        "ip": "1.1.1.1",
        "agent": "Mozilla/5.0",
    }
    if box.token:
        params["sid_token"] = box.token

    response = await request_with_retry(
        "GET",
        GUERRILLAMAIL_BASE,
        params=params,
        provider_name="guerrillamail.com",
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()

    # Response format: {"list": [{"mail_id": "1", "mail_from": "...", "mail_subject": "...", ...}], ...}
    messages = data.get("list", [])
    if not messages:
        return []

    return [
        {
            "id": str(msg.get("mail_id", "")),
            "from": {"address": msg.get("mail_from", "") or ""},
            "subject": msg.get("mail_subject", "") or "",
            "body": "",  # Body needs to be fetched separately with fetch_email
            "timestamp": msg.get("mail_timestamp", 0),
        }
        for msg in messages
        if isinstance(msg, dict)
    ]


async def get_message_body(box: Mailbox, message_id: str) -> dict:
    """Fetch full content of a specific message."""
    params = {
        "f": "fetch_email",
        "email_id": message_id,
        "ip": "1.1.1.1",
        "agent": "Mozilla/5.0",
    }
    if box.token:
        params["sid_token"] = box.token

    response = await request_with_retry(
        "GET",
        GUERRILLAMAIL_BASE,
        params=params,
        provider_name="guerrillamail.com",
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()

    # Response contains mail_body (could be HTML or text)
    return {
        "id": message_id,
        "body": data.get("mail_body", "") or "",
        "text": data.get("mail_body", "") or "",
        "html": data.get("mail_body", "") if "<" in str(data.get("mail_body", "")) else "",
        "subject": data.get("mail_subject", "") or "",
        "from": data.get("mail_from", "") or "",
    }


async def get_message_body_text(box: Mailbox, message_id: str) -> str:
    """Fetch message body as text."""
    result = await get_message_body(box, message_id)
    return result.get("body", "")


async def wait_for_message(
    box: Mailbox,
    from_contains: str = "",
    subject_contains: str = "",
    timeout: int = 120,
    log_fn: LogFn | None = None,
) -> dict | None:
    _log = log_fn or _tprint
    _log(f"Waiting for email (guerrillamail.com, timeout={timeout}s, from='{from_contains}')...")
    deadline = time.monotonic() + timeout
    poll_no = 0

    while time.monotonic() < deadline:
        remaining = int(deadline - time.monotonic())
        poll_no += 1
        _log(f"  [mail] poll #{poll_no} ({remaining}s left)...")
        try:
            msgs = await get_messages(box)
            for msg in msgs:
                sender = msg.get("from", {}).get("address", "")
                subject = msg.get("subject", "")
                from_ok = from_contains.lower() in sender.lower() if from_contains else True
                subj_ok = subject_contains.lower() in subject.lower() if subject_contains else True
                if from_ok and subj_ok:
                    # Fetch full message body
                    full_msg = await get_message_body(box, msg.get("id"))
                    msg["body"] = full_msg.get("body", "")
                    msg["text"] = full_msg.get("text", "")
                    _log(f"  Got: '{subject}' from {sender}")
                    return msg
        except Exception as exc:  # noqa: BLE001 - mail provider best-effort
            _log(f"  Poll error: {exc}")
        await asyncio.sleep(5)

    _log("  Timed out waiting for email")
    return None


async def extend_email_lifetime(box: Mailbox) -> bool:
    """Extend email lifetime by 1 hour."""
    params = {
        "f": "extend",
        "ip": "1.1.1.1",
        "agent": "Mozilla/5.0",
    }
    if box.token:
        params["sid_token"] = box.token

    response = await request_with_retry(
        "GET",
        GUERRILLAMAIL_BASE,
        params=params,
        provider_name="guerrillamail.com",
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    return data.get("success", False)
