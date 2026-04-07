"""
gmail.py � Router: Gmail variations utility + Gmail mailbox management.
T?o v� ki?m tra bi?n th? Gmail (+tag, dot, googlemail) tru?c khi dang k� account m?i.
Qu?n l� Gmail mailboxes (inbox credential d�ng d? dang k� service).

Layer order: Router ? Service ? Provider/DB.
Router kh�ng bi?t g� v? Camoufox, storage_state, hay SQL.
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from ...config.settings import load_config
from ...core.database import (
    block_mailbox_for_service,
    check_gmail_variations_availability,
    delete_mailbox_record,
    get_available_mailboxes_for_service,
    get_mailbox_record,
    get_mailboxes,
    get_service_blocks,
    get_used_gmail_variations,
    unblock_mailbox_for_service,
    upsert_mailbox_record,
)
from ...core.gmail_variations import (
    GmailVariation,
    generate_variations,
    normalize_gmail,
)
from ...core.storage import db_path
from ..exceptions import AppError
from ..schemas import ErrorCode, ok
from ..services.account_service import has_service
from ..services.gmail_inbox_service import (
    MailboxNotFoundError,
    SessionExpiredError,
    extract_otp,
    fetch_body,
    list_inbox,
    poll_for_message,
    search_inbox,
)
from ..services.google_session_service import (
    refresh_all_google_sessions,
    refresh_google_session,
)

_log = logging.getLogger(__name__)
router = APIRouter(prefix="/gmail", tags=["gmail"])

_OPEN_BROWSER_SCRIPT = Path(__file__).parent.parent / "tools" / "open_browser_session.py"


def _db_path():
    return db_path(load_config().base_dir)


def _gmail_cfg():
    return load_config().gmail_variations


def _map_inbox_errors(exc: Exception) -> AppError:
    """Map service-layer exceptions sang HTTP errors � t?p trung t?i 1 ch?."""
    if isinstance(exc, MailboxNotFoundError):
        return AppError(ErrorCode.NOT_FOUND, f"Mailbox khong ton tai: {exc}", 404)
    if isinstance(exc, SessionExpiredError):
        return AppError(
            ErrorCode.SESSION_EXPIRED,
            f"Mailbox {exc} chua co Google session -- refresh-session truoc.",
            422,
        )
    raise exc  # re-raise n?u kh�ng ph?i l?i d� bi?t



# -- Mailbox schemas ------------------------------------------------------------

class UpsertMailboxBody(BaseModel):
    email: str
    app_password: str = ""
    totp_secret: str = ""
    password: str = ""
    source_email: str = ""
    label: str = ""
    disabled: bool = False


class PatchMailboxBody(BaseModel):
    label: str | None = None
    disabled: bool | None = None
    app_password: str | None = None
    totp_secret: str | None = None
    password: str | None = None


# -- Mailbox CRUD ---------------------------------------------------------------

@router.get("/mailboxes")
async def list_mailboxes():
    """Tr? danh s�ch t?t c? Gmail mailboxes."""

    mailboxes = await asyncio.to_thread(get_mailboxes, _db_path())
    summary = [
        {**{k: v for k, v in m.items() if k != "google_auth_state"},
         "google_auth_state": bool(m.get("google_auth_state"))}
        for m in mailboxes
    ]
    return ok(summary)


@router.get("/mailboxes/available")
async def list_available_mailboxes(service: str):
    """Tr? danh s�ch Gmail mailboxes chua b? block cho service.

    Query params:
    - service: t�n service (VD: ELEVENLABS, SENTRY). Required.

    D�ng trong registration flow d? pick mailbox tru?c khi dang k�.
    """

    if not service or not service.strip():
        raise AppError(ErrorCode.VALIDATION, "Query param 'service' kh�ng du?c d? tr?ng", 400)
    mailboxes = await asyncio.to_thread(
        get_available_mailboxes_for_service, _db_path(), service.strip().upper()
    )
    return ok(mailboxes)


@router.post("/mailboxes")
async def upsert_mailbox(body: UpsertMailboxBody):
    """Th�m ho?c c?p nh?t m?t Gmail mailbox."""

    from ...core.gmail_variations import _parse_gmail

    if not _parse_gmail(body.email):
        raise AppError(ErrorCode.VALIDATION, f"Kh�ng ph?i Gmail h?p l?: {body.email!r}", 400)

    canonical = normalize_gmail(body.email)
    mailbox = await asyncio.to_thread(
        upsert_mailbox_record,
        _db_path(), canonical, body.app_password, body.totp_secret,
        body.password, body.source_email, body.label, body.disabled,
    )
    return ok(mailbox)


@router.patch("/mailboxes/{email}")
async def patch_mailbox(email: str, body: PatchMailboxBody):
    """C?p nh?t partial fields c?a Gmail mailbox (ch? field n�o du?c truy?n m?i update).

    D�ng d? enable/disable mailbox, d?i label, c?p nh?t password/totp ri�ng l?.
    """


    record = await asyncio.to_thread(get_mailbox_record, _db_path(), email)
    if not record:
        raise AppError(ErrorCode.NOT_FOUND, f"Mailbox kh�ng t?n t?i: {email!r}", 404)

    # Merge: ch? override field n�o body g?i (kh�ng None)
    updated = await asyncio.to_thread(
        upsert_mailbox_record,
        _db_path(),
        record["email"],
        record["app_password"]  if body.app_password  is None else body.app_password,
        record["totp_secret"]   if body.totp_secret   is None else body.totp_secret,
        record["password"]      if body.password       is None else body.password,
        record.get("source_email", ""),
        record["label"]         if body.label          is None else body.label,
        record["disabled"]      if body.disabled       is None else body.disabled,
    )
    return ok(updated)


# -- Service Blocks -------------------------------------------------------------

class BlockBody(BaseModel):
    service: str
    reason: str = ""


@router.get("/mailboxes/blocks")
async def list_blocks(service: str | None = None):
    """Tr? danh s�ch t?t c? mailbox service blocks. L?c theo ?service=ELEVENLABS n?u c?n."""

    blocks = await asyncio.to_thread(get_service_blocks, _db_path(), service)
    return ok(blocks)


@router.delete("/mailboxes/{email}")
async def delete_mailbox(email: str):
    """X�a m?t Gmail mailbox."""

    deleted = await asyncio.to_thread(delete_mailbox_record, _db_path(), email)
    if not deleted:
        raise AppError(ErrorCode.NOT_FOUND, f"Mailbox kh�ng t?n t?i: {email!r}", 404)
    return ok({"deleted": True})


# -- Gmail Inbox ----------------------------------------------------------------

@router.get("/mailboxes/{email}/messages")
async def gmail_list_messages(email: str, unread_only: bool = False):
    """L?y danh s�ch emails t? Gmail inbox.

    Query params:
    - unread_only: ch? tr? unread emails (m?c d?nh false).
    """
    try:
        msgs = await list_inbox(_db_path(), email, unread_only)
    except (MailboxNotFoundError, SessionExpiredError) as exc:
        raise _map_inbox_errors(exc)
    return ok(msgs)


@router.get("/mailboxes/{email}/messages/search")
async def gmail_search_messages(email: str, q: str):
    """T�m ki?m emails b?ng Gmail search query.

    Query params:
    - q: Gmail search query, VD: "from:noreply@elevenlabs.io" ho?c "subject:verify".
    """
    if not q or not q.strip():
        raise AppError(ErrorCode.VALIDATION, "Query param 'q' khong duoc de trong", 400)
    try:
        msgs = await search_inbox(_db_path(), email, q.strip())
    except (MailboxNotFoundError, SessionExpiredError) as exc:
        raise _map_inbox_errors(exc)
    return ok(msgs)


@router.get("/mailboxes/{email}/messages/{message_id}/body")
async def gmail_get_message_body(email: str, message_id: str):
    """L?y n?i dung HTML c?a email theo jsthread ID.

    message_id: gi� tr? jsthread t? list/search messages API (VD: ":2w").
    """
    try:
        body = await fetch_body(_db_path(), email, message_id)
    except (MailboxNotFoundError, SessionExpiredError) as exc:
        raise _map_inbox_errors(exc)
    return ok({"message_id": message_id, "body": body})


@router.get("/mailboxes/{email}/messages/{message_id}/otp")
async def gmail_get_message_otp(email: str, message_id: str, digits: int = 6):
    """Extract OTP/verification code t? n?i dung email.

    T�m s? c� d? d�i `digits` ch? s? trong email body (m?c d?nh 6).
    Tr? code d?u ti�n t�m du?c (thu?ng l� code n?i b?t nh?t trong email).

    Query params:
    - digits: s? ch? s? c?a OTP (m?c d?nh 6, thu?ng l� 4-8).

    Raise 422 n?u kh�ng t�m th?y OTP trong email.
    """
    if digits < 4 or digits > 10:
        raise AppError(ErrorCode.VALIDATION, "digits phai trong khoang 4-10", 400)
    try:
        result = await extract_otp(_db_path(), email, message_id, digits)
    except (MailboxNotFoundError, SessionExpiredError) as exc:
        raise _map_inbox_errors(exc)
    except ValueError as exc:
        raise AppError(ErrorCode.NOT_FOUND, str(exc), 422)
    return ok(result)


class WaitForMessageBody(BaseModel):
    from_contains: str = ""
    subject_contains: str = ""
    timeout: int = 120
    poll_interval: int = 12


@router.post("/mailboxes/{email}/wait-for-message")
async def gmail_wait_for_message(email: str, body: WaitForMessageBody):
    """Poll Gmail inbox d?n khi t�m du?c email kh?p filter ho?c timeout.

    D�ng trong registration flow d? d?i verification email.
    Tr? null trong data n?u timeout.
    """
    if body.timeout < 1 or body.timeout > 600:
        raise AppError(ErrorCode.VALIDATION, "timeout phai trong khoang 1-600 giay", 400)
    try:
        msg = await poll_for_message(
            _db_path(), email,
            from_contains=body.from_contains,
            subject_contains=body.subject_contains,
            timeout=body.timeout,
            poll_interval=body.poll_interval,
        )
    except (MailboxNotFoundError, SessionExpiredError) as exc:
        raise _map_inbox_errors(exc)
    return ok(msg)


@router.get("/mailboxes/{email}")
async def get_mailbox(email: str):
    """L?y th�ng tin m?t Gmail mailbox."""

    mailbox = await asyncio.to_thread(get_mailbox_record, _db_path(), email)
    if not mailbox:
        raise AppError(ErrorCode.NOT_FOUND, f"Mailbox kh�ng t?n t?i: {email!r}", 404)
    return ok(mailbox)


# -- Google Session -------------------------------------------------------------

@router.post("/mailboxes/refresh-all-sessions")
async def refresh_all_mailbox_sessions():
    """Login Google cho t?t c? mailboxes c� password (sequential). Tr? list k?t qu?."""
    results = await refresh_all_google_sessions()
    ok_count  = sum(1 for r in results if r.get("ok"))
    fail_count = sum(1 for r in results if not r.get("ok"))
    return ok({"results": results, "ok": ok_count, "fail": fail_count, "total": len(results)})


@router.post("/mailboxes/{email}/refresh-session")
async def refresh_mailbox_session(email: str):
    """Login Google b?ng Playwright v� luu storage_state cho 1 mailbox."""
    try:
        result = await refresh_google_session(email)
    except ValueError as e:
        raise AppError(ErrorCode.VALIDATION, str(e), 400)
    return ok(result)




@router.post("/mailboxes/{email}/open-browser")
async def open_mailbox_browser(email: str):
    """Mo Camoufox browser voi stored Google session cho mailbox (subprocess, non-blocking)."""

    _log.info("open_mailbox_browser: request for email=%s", email)
    mailbox = await asyncio.to_thread(get_mailbox_record, _db_path(), email)
    if not mailbox:
        _log.warning("open_mailbox_browser: mailbox not found � email=%s", email)
        raise AppError(ErrorCode.NOT_FOUND, f"Mailbox khong ton tai: {email!r}", 404)
    if not mailbox.get("google_auth_state"):
        _log.warning("open_mailbox_browser: no google_auth_state � email=%s", email)
        raise AppError(ErrorCode.VALIDATION, f"Mailbox {email!r} chua co session - refresh-session truoc", 400)
    args = [sys.executable, str(_OPEN_BROWSER_SCRIPT), "GMAIL", email]
    _log.info("open_mailbox_browser: spawning subprocess � args=%s", args)
    proc = subprocess.Popen(
        args,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )
    _log.info("open_mailbox_browser: subprocess PID=%s launched for %s", proc.pid, email)
    return ok({"launched": True, "pid": proc.pid})


@router.get("/mailboxes/{email}/totp")
async def get_totp_code(email: str):
    """Generate TOTP code hi?n t?i cho mailbox."""

    import time

    import pyotp

    mailbox = await asyncio.to_thread(get_mailbox_record, _db_path(), email)
    if not mailbox:
        raise AppError(ErrorCode.NOT_FOUND, f"Mailbox kh�ng t?n t?i: {email!r}", 404)
    secret = (mailbox.get("totp_secret") or "").strip()
    if not secret:
        raise AppError(ErrorCode.VALIDATION, f"Mailbox {email!r} kh�ng c� TOTP secret", 400)
    totp = pyotp.TOTP(secret.replace(" ", "").upper())
    code = totp.now()
    remaining = totp.interval - (int(time.time()) % totp.interval)
    return ok({"code": code, "remaining": remaining, "interval": totp.interval})

@router.post("/mailboxes/{email}/blocks")
async def add_block(email: str, body: BlockBody):
    """��nh d?u mailbox kh�ng kh? d?ng cho m?t service."""

    await asyncio.to_thread(block_mailbox_for_service, _db_path(), email, body.service, body.reason)
    return ok({"email": email, "service": body.service.upper(), "blocked": True})


@router.delete("/mailboxes/{email}/blocks/{service}")
async def remove_block(email: str, service: str):
    """X�a block c?a mailbox cho service."""

    deleted = await asyncio.to_thread(unblock_mailbox_for_service, _db_path(), email, service)
    if not deleted:
        raise AppError(ErrorCode.NOT_FOUND, f"Block kh�ng t?n t?i: {email!r} / {service!r}", 404)
    return ok({"email": email, "service": service.upper(), "blocked": False})


# -- Variations -----------------------------------------------------------------

class GenerateVariationsBody(BaseModel):
    base_email: str
    service: str                          # Service s? dang k� (d? check DB)
    use_plus: bool = True
    use_dot: bool = True
    use_googlemail: bool = True
    plus_tags: list[str] | None = None  # None ? d�ng default_plus_tags t? config


class VariationResult(BaseModel):
    email: str
    technique: str          # "plus" | "dot" | "googlemail"
    tag: str | None
    available: bool         # True = chua c� trong DB cho service n�y


@router.get("/variations/defaults")
async def get_variation_defaults():
    """Tr? v? config defaults cho GmailVariationsModal � FE d�ng d? kh?i t?o state."""
    cfg = _gmail_cfg()
    return ok({
        "use_plus":            cfg.ui_default_use_plus,
        "use_dot":             cfg.ui_default_use_dot,
        "use_googlemail":      cfg.ui_default_use_googlemail,
        "plus_tags":           cfg.ui_default_plus_tags,
        "dot_max_username_len": cfg.dot_max_username_len,
    })


@router.post("/variations")
async def get_variations(body: GenerateVariationsBody):
    """
    T?o t?t c? Gmail variations t? base_email v� ki?m tra xem c�i n�o c�n available
    cho service d� ch? d?nh.
    """

    from ...core.gmail_variations import _parse_gmail

    if not _parse_gmail(body.base_email):
        raise AppError(ErrorCode.VALIDATION, f"Kh�ng ph?i Gmail h?p l?: {body.base_email!r}", 400)
    if not await has_service(body.service):
        raise AppError(ErrorCode.UNSUPPORTED, f"Unsupported service: {body.service}", 400)

    cfg = _gmail_cfg()
    effective_tags = list(body.plus_tags) if body.plus_tags is not None else list(cfg.default_plus_tags)

    variations: list[GmailVariation] = generate_variations(
        base_email=body.base_email,
        use_plus=body.use_plus,
        use_dot=body.use_dot,
        use_googlemail=body.use_googlemail,
        plus_tags=effective_tags,
        dot_max_username_len=cfg.dot_max_username_len,
        dot_long_sample_mid_divisor=cfg.dot_long_sample_mid_divisor,
    )

    emails = [v.email for v in variations]
    availability = await asyncio.to_thread(
        check_gmail_variations_availability, _db_path(), emails, body.service
    )

    results = [
        {
            "email":     v.email,
            "technique": v.technique,
            "tag":       v.tag,
            "available": availability.get(v.email, True),
        }
        for v in variations
    ]

    canonical = normalize_gmail(body.base_email)
    return ok({
        "base_email":  canonical,
        "service":     body.service.upper(),
        "total":       len(results),
        "available":   sum(1 for r in results if r["available"]),
        "variations":  results,
    })


@router.get("/used")
async def get_used(base_email: str, service: str | None = None):
    """
    L?y danh s�ch accounts d� d�ng variations c?a base_email (k? c? ch�nh email d�).
    """

    from ...core.gmail_variations import _parse_gmail

    if not _parse_gmail(base_email):
        raise AppError(ErrorCode.VALIDATION, f"Kh�ng ph?i Gmail h?p l?: {base_email!r}", 400)
    if service and not await has_service(service):
        raise AppError(ErrorCode.UNSUPPORTED, f"Unsupported service: {service}", 400)

    canonical = normalize_gmail(base_email)
    accounts = await asyncio.to_thread(
        get_used_gmail_variations, _db_path(), canonical, service
    )
    return ok({
        "base_email": canonical,
        "service":    service.upper() if service else None,
        "count":      len(accounts),
        "accounts":   accounts,
    })

