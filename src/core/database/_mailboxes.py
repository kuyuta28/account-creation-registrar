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

# Sentinel for "do not change this column" semantics in upsert_mailbox_record.
# Callers can pass `_UNSET` (or omit the kwarg) to leave the column untouched on
# conflict. Passing "" (or any other value, including None) overwrites the
# existing value with that value. This prevents the historical bug where a
# PATCH/POST that did not mention totp_secret wiped the stored secret to ''.
_UNSET: Any = object()

from ._engine import (
    _Account, _AccountGmail, _MailboxServiceBlock, _get_engine, _now,
    _to_mailbox_dict,
)
from ._services import _ensure_service_exists


# ── Mailbox CRUD ──────────────────────────────────────────────────────────────

def _get_gmail_ext(s, row: _Account) -> _AccountGmail | None:
    return s.scalars(
        select(_AccountGmail).where(_AccountGmail.account_id == row.id)
    ).first()


def _get_gmail_exts(s, rows: list[_Account]) -> dict[int, _AccountGmail]:
    if not rows:
        return {}
    ids = [r.id for r in rows]
    exts = s.scalars(select(_AccountGmail).where(_AccountGmail.account_id.in_(ids))).all()
    return {ext.account_id: ext for ext in exts}


def get_mailboxes(db_path: Path) -> list[dict[str, Any]]:
    """Trả tất cả Gmail mailboxes, sắp xếp theo email."""
    if not db_path.exists():
        return []
    with Session(_get_engine(db_path)) as s:
        rows = s.scalars(
            select(_Account).where(_Account.service == "GMAIL").order_by(_Account.email)
        ).all()
        ext_map = _get_gmail_exts(s, rows)
    return [_to_mailbox_dict(r, ext_map.get(r.id)) for r in rows]


def get_mailbox_record(db_path: Path, email: str) -> dict[str, Any] | None:
    canonical = email.strip().lower()
    with Session(_get_engine(db_path)) as s:
        row = s.scalars(
            select(_Account).where(_Account.service == "GMAIL", _Account.email == canonical)
        ).first()
        if row is None:
            return None
        ext = _get_gmail_ext(s, row)
    return _to_mailbox_dict(row, ext)


def upsert_mailbox_record(
    db_path: Path,
    email: str,
    app_password: Any = _UNSET,
    totp_secret: Any = _UNSET,
    password: Any = _UNSET,
    source_email: Any = _UNSET,
    label: Any = _UNSET,
    disabled: Any = _UNSET,
) -> dict[str, Any]:
    """Insert hoặc update Gmail mailbox. Trả về dict mailbox sau khi lưu.

    Important contract:
      - Each "settable" parameter defaults to `_UNSET`, NOT to "" or None.
      - On INSERT (no existing row): missing fields are filled with the schema
        defaults (typically ""), same as the column defaults.
      - On UPDATE (row already exists): only the fields the caller actually
        passes (i.e. anything other than `_UNSET`) are written. Anything left
        as `_UNSET` is preserved from the existing row. This prevents the
        historical bug where a PATCH/POST that did not mention `totp_secret`
        silently wiped the stored secret to "".
      - If the caller wants to explicitly CLEAR a field (e.g. totp_secret=""),
        they pass the empty string. That is a deliberate write.
    """
    canonical = email.strip().lower()
    now = _now()
    with Session(_get_engine(db_path)) as s:
        _ensure_service_exists(s, "GMAIL")

        existing = s.scalars(
            select(_Account).where(_Account.service == "GMAIL", _Account.email == canonical)
        ).first()

        if existing is None:
            # INSERT: only fill the columns the caller mentioned. Anything
            # _UNSET falls back to the column default at the SQLAlchemy layer.
            insert_values: dict[str, Any] = {
                "service": "GMAIL", "email": canonical,
                "session_state": "", "check_status": "", "last_checked": "",
                "last_error": "", "created_at": now, "updated_at": now,
            }
            if password     is not _UNSET: insert_values["password"]     = password
            if source_email is not _UNSET: insert_values["source_email"] = source_email
            if disabled     is not _UNSET: insert_values["disabled"]     = disabled
            s.execute(sqlite_insert(_Account).values(**insert_values))
            s.flush()
            row = s.scalars(
                select(_Account).where(_Account.service == "GMAIL", _Account.email == canonical)
            ).first()
        else:
            # UPDATE: only write fields the caller explicitly passed.
            update_values: dict[str, Any] = {"updated_at": now}
            if password     is not _UNSET: update_values["password"]     = password
            if source_email is not _UNSET: update_values["source_email"] = source_email
            if disabled     is not _UNSET: update_values["disabled"]     = disabled
            if update_values.keys() != {"updated_at"}:
                s.execute(
                    update(_Account)
                    .where(_Account.service == "GMAIL", _Account.email == canonical)
                    .values(**update_values)
                )
            row = existing

        # Gmail extension row: same contract.
        assert row is not None
        ext_existing = _get_gmail_ext(s, row)
        if ext_existing is None:
            ext_values: dict[str, Any] = {"account_id": row.id}
            if app_password is not _UNSET: ext_values["app_password"] = app_password
            if totp_secret  is not _UNSET: ext_values["totp_secret"]  = totp_secret
            if label        is not _UNSET: ext_values["label"]        = label
            s.execute(sqlite_insert(_AccountGmail).values(**ext_values))
        else:
            ext_update: dict[str, Any] = {}
            if app_password is not _UNSET: ext_update["app_password"] = app_password
            if totp_secret  is not _UNSET: ext_update["totp_secret"]  = totp_secret
            if label        is not _UNSET: ext_update["label"]        = label
            if ext_update:
                s.execute(
                    update(_AccountGmail)
                    .where(_AccountGmail.account_id == row.id)
                    .values(**ext_update)
                )

        s.commit()
        ext = _get_gmail_ext(s, row)
    return _to_mailbox_dict(row, ext)  # type: ignore[arg-type]


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
        "label":      row.source_email or "",   # label stored in source_email column
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
            source_email=label,  # label stored in source_email column
            disabled=disabled,
            created_at=now,
            updated_at=now,
            password="",
            check_status="",
            last_checked="",
            last_error="",
            session_state="",
        )
        .on_conflict_do_update(
            index_elements=["service", "email"],
            set_={"source_email": label, "disabled": disabled, "updated_at": now},
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
