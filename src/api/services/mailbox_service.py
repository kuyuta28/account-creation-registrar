"""
mailbox_service.py — In-memory temp mailbox management for manual use.
FP style: module-level state + pure async functions.
"""
from __future__ import annotations

import asyncio
import re
import time
import uuid
from typing import Any

from ...mail.client import (
    Mailbox,
    create_mailbox,
    get_message_body,
    get_messages,
)
from common.database._async import get_provider_connection_strs_async

# ── In-memory store ───────────────────────────────────────────────────

_active_boxes: dict[str, Mailbox] = {}          # email -> Mailbox
_created_at: dict[str, float] = {}              # email -> timestamp

# ── Mailbox creation jobs (fire-and-forget) ──────────────────────────
# Pattern: POST /mailbox returns 202 {job_id}; GET /mailbox/jobs/{id}
# polls status. Frontend polls and shows toast when done/failed.
# In-memory only — single-process dev stack. Restart wipes jobs.

_JOB_TTL_SEC = 300  # evict finished jobs after 5 min


class _MailboxJob:
    __slots__ = ("id", "status", "provider", "result", "error", "created_at", "finished_at")

    def __init__(self, id: str, provider: str | None) -> None:
        self.id = id
        self.provider = provider
        self.status = "pending"
        self.result: dict[str, Any] | None = None
        self.error: str | None = None
        self.created_at = time.time()
        self.finished_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "status": self.status,
            "provider": self.provider,
            "created_at": self.created_at,
        }
        if self.result is not None:
            d["result"] = self.result
        if self.error is not None:
            d["error"] = self.error
        if self.finished_at is not None:
            d["finished_at"] = self.finished_at
        return d


_jobs: dict[str, _MailboxJob] = {}


def _evict_old_jobs() -> None:
    """Evict finished jobs older than _JOB_TTL_SEC. Called on each new job."""
    now = time.time()
    stale = [
        jid for jid, j in _jobs.items()
        if j.finished_at is not None and now - j.finished_at > _JOB_TTL_SEC
    ]
    for jid in stale:
        _jobs.pop(jid, None)


async def _run_create_job(job_id: str, provider: str | None) -> None:
    """Background task: thực sự tạo mailbox, update job state."""
    job = _jobs.get(job_id)
    if not job:
        return
    job.status = "running"
    try:
        result = await create_new_mailbox(provider)
        job.result = result
        job.status = "done"
    except Exception as e:  # noqa: BLE001 — boundary: report to caller
        job.error = f"{type(e).__name__}: {e}"
        job.status = "failed"
    finally:
        job.finished_at = time.time()


def start_create_mailbox_job(provider: str | None) -> str:
    """Tạo job + fire-and-forget background task. Return job_id ngay."""
    _evict_old_jobs()
    job_id = uuid.uuid4().hex
    _jobs[job_id] = _MailboxJob(id=job_id, provider=provider)
    asyncio.create_task(_run_create_job(job_id, provider))
    return job_id


def get_mailbox_job(job_id: str) -> dict[str, Any] | None:
    """Trả job state cho polling. None nếu job_id không tồn tại."""
    job = _jobs.get(job_id)
    return job.to_dict() if job else None


async def create_new_mailbox(provider: str | None = None) -> dict[str, Any]:
    """Create a new temp mailbox using the given provider (or default)."""
    # Lấy tất cả active providers; filter theo provider_type prefix trong code dưới.
    # Không filter theo service_tag vì UI dropdown chọn provider type, không phải tag.
    all_p = await get_provider_connection_strs_async(service_tag=None)

    if provider == "mail.tm":
        providers = [p for p in all_p if p.startswith("https://") or p.startswith("mail.tm:")]
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
