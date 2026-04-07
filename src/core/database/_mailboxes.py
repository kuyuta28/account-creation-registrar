"""
database/_mailboxes.py — Gmail mailbox CRUD + service blocks.
Mailboxes are stored as accounts(service='GMAIL').
Label field is now fully supported per API docs.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ._engine import (
    _Account, _MailboxServiceBlock, _get_engine, _now,
    _to_mailbox_dict,
)
from ._services import _ensure_service_exists


# ── Mailbox CRUD ──────────────────────────────────────────────────────────────

def get_mailboxes(db_path: Path) -> list[dict[str, Any]]:
    """Trả tất cả Gmail mailboxes, sắp xếp theo email."""
    if not db_path.exists():
        return []
    with Session(_get_engine(db_path)) as s:
        rows = s.scalars(
            select(_Account).where(_Account.service == "GMAIL").order_by(_Account.email)
        ).all()
    return [_to_mailbox_dict(r) for r in rows]


def get_mailbox_record(db_path: Path, email: str) -> dict[str, Any] | None:
    canonical = email.strip().lower()
    with Session(_get_engine(db_path)) as s:
        row = s.scalars(
            select(_Account).where(_Account.service == "GMAIL", _Account.email == canonical)
        ).first()
    return _to_mailbox_dict(row) if row else None


def upsert_mailbox_record(
    db_path: Path,
    email: str,
    app_password: str = "",
    totp_secret: str = "",
    password: str = "",
    source_email: str = "",
    label: str = "",
    disabled: bool = False,
) -> dict[str, Any]:
    """Insert hoặc update Gmail mailbox. Trả về dict mailbox sau khi lưu."""
    canonical = email.strip().lower()
    now = _now()
    stmt = (
        sqlite_insert(_Account)
        .values(
            service="GMAIL",
            email=canonical,
            app_password=app_password,
            totp_secret=totp_secret,
            password=password,
            source_email=source_email,
            label=label,
            disabled=disabled,
            created_at=now,
            updated_at=now,
            api_key="", credits=0, refresh_token="", access_token="",
            account_id="", id_token="", expired="", last_refresh="",
            token_type="", check_status="", quota_pct="", last_checked="",
            last_error="", session_state="",
        )
        .on_conflict_do_update(
            index_elements=["service", "email"],
            set_={
                "app_password": app_password,
                "totp_secret":  totp_secret,
                "password":     password,
                "source_email": source_email,
                "label":        label,
                "disabled":     disabled,
                "updated_at":   now,
            },
        )
    )
    with Session(_get_engine(db_path)) as s:
        _ensure_service_exists(s, "GMAIL")
        s.execute(stmt)
        s.commit()
        row = s.scalars(
            select(_Account).where(_Account.service == "GMAIL", _Account.email == canonical)
        ).first()
    return _to_mailbox_dict(row)  # type: ignore[arg-type]


def delete_mailbox_record(db_path: Path, email: str) -> bool:
    canonical = email.strip().lower()
    with Session(_get_engine(db_path)) as s:
        result = s.execute(
            delete(_Account).where(_Account.service == "GMAIL", _Account.email == canonical)
        )
        s.commit()
    return result.rowcount > 0


def save_mailbox_google_auth_state(db_path: Path, email: str, auth_state_json: str) -> bool:
    """Lưu Playwright storage_state JSON vào accounts.session_state."""
    canonical = email.strip().lower()
    now = _now()
    with Session(_get_engine(db_path)) as s:
        result = s.execute(
            update(_Account)
            .where(_Account.service == "GMAIL", _Account.email == canonical)
            .values(session_state=auth_state_json, updated_at=now)
        )
        s.commit()
    return result.rowcount > 0


def get_mailbox_google_auth_state(db_path: Path, email: str) -> str | None:
    canonical = email.strip().lower()
    with Session(_get_engine(db_path)) as s:
        row = s.scalars(
            select(_Account).where(_Account.service == "GMAIL", _Account.email == canonical)
        ).first()
    if row is None:
        return None
    return row.session_state or None


# ── Mailbox Service Blocks ─────────────────────────────────────────────────────

def block_mailbox_for_service(
    db_path: Path,
    email: str,
    service: str,
    reason: str = "",
) -> None:
    canonical = email.strip().lower()
    svc = service.upper()
    now = _now()
    stmt = (
        sqlite_insert(_MailboxServiceBlock)
        .values(email=canonical, service=svc, reason=reason, blocked_at=now)
        .on_conflict_do_update(
            index_elements=["email", "service"],
            set_={"reason": reason, "blocked_at": now},
        )
    )
    with Session(_get_engine(db_path)) as s:
        s.execute(stmt)
        s.commit()


def unblock_mailbox_for_service(db_path: Path, email: str, service: str) -> bool:
    canonical = email.strip().lower()
    svc = service.upper()
    with Session(_get_engine(db_path)) as s:
        result = s.execute(
            delete(_MailboxServiceBlock).where(
                _MailboxServiceBlock.email == canonical,
                _MailboxServiceBlock.service == svc,
            )
        )
        s.commit()
    return result.rowcount > 0


def is_mailbox_blocked_for_service(db_path: Path, email: str, service: str) -> bool:
    canonical = email.strip().lower()
    svc = service.upper()
    with Session(_get_engine(db_path)) as s:
        row = s.get(_MailboxServiceBlock, (canonical, svc))
    return row is not None


def get_available_mailboxes_for_service(db_path: Path, service: str) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    svc = service.upper()
    blocked_emails = select(_MailboxServiceBlock.email).where(
        _MailboxServiceBlock.service == svc
    )
    stmt = (
        select(_Account)
        .where(_Account.service == "GMAIL")
        .where(_Account.disabled == False)   # noqa: E712
        .where(_Account.email.not_in(blocked_emails))
        .order_by(_Account.email)
    )
    with Session(_get_engine(db_path)) as s:
        rows = s.scalars(stmt).all()
    return [_to_mailbox_dict(r) for r in rows]


def get_service_blocks(db_path: Path, service: str | None = None) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    stmt = select(_MailboxServiceBlock)
    if service is not None:
        stmt = stmt.where(_MailboxServiceBlock.service == service.upper())
    stmt = stmt.order_by(_MailboxServiceBlock.service, _MailboxServiceBlock.email)
    with Session(_get_engine(db_path)) as s:
        rows = s.scalars(stmt).all()
    return [
        {"email": r.email, "service": r.service, "reason": r.reason, "blocked_at": r.blocked_at}
        for r in rows
    ]


# ── SMS Phone CRUD ─────────────────────────────────────────────────────────────

def _to_sms_phone_dict(row: _Account) -> dict[str, Any]:
    return {
        "phone":      row.email,   # phone number stored in email column
        "label":      row.label,
        "disabled":   row.disabled,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def get_sms_phones(db_path: Path) -> list[dict[str, Any]]:
    """Trả tất cả SIM phone numbers, sắp xếp theo phone."""
    if not db_path.exists():
        return []
    with Session(_get_engine(db_path)) as s:
        rows = s.scalars(
            select(_Account).where(_Account.service == "SMS").order_by(_Account.email)
        ).all()
    return [_to_sms_phone_dict(r) for r in rows]


def upsert_sms_phone(
    db_path: Path,
    phone: str,
    label: str = "",
    disabled: bool = False,
) -> dict[str, Any]:
    """Insert hoặc update SIM phone. Trả về dict sau khi lưu."""
    # Normalize: strip spaces/dashes, keep leading +
    normalized = phone.strip().replace(" ", "").replace("-", "")
    now = _now()
    stmt = (
        sqlite_insert(_Account)
        .values(
            service="SMS",
            email=normalized,
            label=label,
            disabled=disabled,
            created_at=now,
            updated_at=now,
            password="", app_password="", totp_secret="", source_email="",
            api_key="", credits=0, refresh_token="", access_token="",
            account_id="", id_token="", expired="", last_refresh="",
            token_type="", check_status="", quota_pct="", last_checked="",
            last_error="", session_state="",
        )
        .on_conflict_do_update(
            index_elements=["service", "email"],
            set_={"label": label, "disabled": disabled, "updated_at": now},
        )
    )
    with Session(_get_engine(db_path)) as s:
        _ensure_service_exists(s, "SMS")
        s.execute(stmt)
        s.commit()
        row = s.scalars(
            select(_Account).where(_Account.service == "SMS", _Account.email == normalized)
        ).first()
    return _to_sms_phone_dict(row)  # type: ignore[arg-type]


def delete_sms_phone(db_path: Path, phone: str) -> bool:
    normalized = phone.strip().replace(" ", "").replace("-", "")
    with Session(_get_engine(db_path)) as s:
        result = s.execute(
            delete(_Account).where(_Account.service == "SMS", _Account.email == normalized)
        )
        s.commit()
    return result.rowcount > 0
