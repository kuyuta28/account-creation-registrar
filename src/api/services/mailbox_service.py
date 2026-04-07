"""
mailbox_service.py — In-memory temp mailbox management for manual use.
FP style: module-level state + pure async functions.
"""
from __future__ import annotations

import re
import time
from typing import Any

from ...mail.client import (
    Mailbox,
    create_mailbox,
    get_message_body,
    get_messages,
)

# ── In-memory store ───────────────────────────────────────────────────

_active_boxes: dict[str, Mailbox] = {}          # email -> Mailbox
_created_at: dict[str, float] = {}              # email -> timestamp


async def create_new_mailbox(provider: str | None = None) -> dict[str, Any]:
    """Create a new temp mailbox using the given provider (or default)."""
    from ...config.settings import load_config
    cfg = load_config()

    all_p = cfg.mail.providers_for()  # all active providers from DB

    if provider == "mailslurp":
        providers = [p for p in all_p if p.startswith("mailslurp.com:")]
        if not providers:
            raise RuntimeError("No MailSlurp API keys configured in DB")
    elif provider == "mail.tm":
        providers = [p for p in all_p if p.startswith("https://")]
        if not providers:
            raise RuntimeError("No mail.tm providers configured in DB")
    elif provider == "testmail.app":
        providers = [p for p in all_p if p.startswith("testmail.app:")]
        if not providers:
            raise RuntimeError("No testmail.app accounts configured in DB")
    elif provider == "mailosaur":
        providers = [p for p in all_p if p.startswith("mailosaur.com:")]
        if not providers:
            raise RuntimeError("No Mailosaur API keys configured in DB")
    elif provider == "guerrillamail":
        providers = ["guerrillamail.com"]
    elif provider:
        providers = [provider]
    else:
        providers = list(all_p) if all_p else None

    box = await create_mailbox(providers)
    _active_boxes[box.email] = box
    _created_at[box.email] = time.time()
    return {
        "email": box.email,
        "provider": box.provider,
        "created_at": _created_at[box.email],
    }


def list_active_mailboxes() -> list[dict[str, Any]]:
    """List all active mailboxes."""
    return [
        {
            "email": email,
            "provider": box.provider,
            "created_at": _created_at.get(email, 0),
        }
        for email, box in _active_boxes.items()
    ]


def remove_mailbox(email: str) -> bool:
    """Remove a mailbox from active list."""
    removed = _active_boxes.pop(email, None)
    _created_at.pop(email, None)
    return removed is not None


async def fetch_messages(email: str) -> list[dict[str, Any]]:
    """Fetch all messages for an active mailbox."""
    box = _active_boxes.get(email)
    if not box:
        raise KeyError(f"Mailbox {email} not found")

    raw_messages = await get_messages(box)
    result = []
    for msg in raw_messages:
        mid = msg.get("id", "")
        sender = msg.get("from", {})
        if isinstance(sender, dict):
            sender_addr = sender.get("address", "")
        else:
            sender_addr = str(sender)

        result.append({
            "id": mid,
            "from": sender_addr,
            "subject": msg.get("subject", ""),
            "has_body": bool(msg.get("body", "")),
        })
    return result


# Domains/patterns to skip when extracting links from emails
_JUNK_LINK_PATTERNS = re.compile(
    r"w3\.org|xmlns|schema\.org|opentype\.org|microsoft\.com/office"
    r"|fonts\.googleapis|fonts\.gstatic"
    r"|favicon|\.png$|\.jpg$|\.gif$|\.ico$|\.svg$|\.woff2?$|\.css$"
    r"|list-manage\.com/(track|vcard)|mailchimp\.com"
    r"|unsubscribe|manage.preferences|email-preferences",
    re.IGNORECASE,
)

# OTP-like patterns: "code: 1234", "OTP is 582910", "mã: 4829", etc.
_OTP_PATTERNS = [
    re.compile(r"(?:code|mã|otp|pin|token)[:\s\-—=]+(\d{4,8})\b", re.IGNORECASE),
    re.compile(r"(?:code|mã|otp|pin|token)\s+is\s+(\d{4,8})\b", re.IGNORECASE),
    re.compile(r"\b(\d{4,8})\s*(?:is your|là mã)", re.IGNORECASE),
    re.compile(r"(?:enter|use|nhập|dùng)[:\s]+(\d{4,8})\b", re.IGNORECASE),
]

# Fallback: standalone big number (6+ digits) not looking like a year
_OTP_FALLBACK = re.compile(r"\b(\d{6,8})\b")


def _extract_otp(text: str) -> str | None:
    """Smart OTP extraction — tries specific patterns first, then fallback."""
    for pat in _OTP_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(1)
    # Fallback: 6-8 digit numbers (skip 4-5 to avoid years/zip codes)
    m = _OTP_FALLBACK.search(text)
    if m:
        return m.group(1)
    return None


def _extract_links(body: str) -> list[str]:
    """Extract actionable links, filtering out junk (DTD, images, tracking)."""
    raw = re.findall(r"https?://[^\s'\"<>)}\]]+", body)
    seen: set[str] = set()
    result: list[str] = []
    for url in raw:
        # Clean trailing punctuation
        url = url.rstrip(".,;:!?")
        if url in seen or _JUNK_LINK_PATTERNS.search(url):
            continue
        seen.add(url)
        result.append(url)
        if len(result) >= 10:
            break
    return result


def _html_to_text(html: str) -> str:
    """Minimal HTML to plain text — strips tags, decodes entities."""
    import html as html_mod
    text = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|tr|li|h[1-6])>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_mod.unescape(text)
    # Collapse blank lines
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


async def fetch_message_detail(email: str, message_id: str) -> dict[str, Any]:
    """Fetch full body of a specific message."""
    box = _active_boxes.get(email)
    if not box:
        raise KeyError(f"Mailbox {email} not found")

    body = await get_message_body(box, message_id)
    is_html = bool(re.search(r"<(html|body|div|table|p)\b", body, re.IGNORECASE))
    plain = _html_to_text(body) if is_html else body

    return {
        "id": message_id,
        "body": body,
        "text": plain,
        "is_html": is_html,
        "links": _extract_links(body),
        "otp": _extract_otp(plain),
    }
