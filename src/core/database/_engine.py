"""
database/_engine.py — ORM models, engine cache, and row serializers.

Internal module — callers use database/__init__.py public API.
"""
from __future__ import annotations

from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Boolean, Engine, Index, Integer, String, Text, UniqueConstraint,
    create_engine, event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import NullPool


# ── ORM Models ────────────────────────────────────────────────────────────────

class _Base(DeclarativeBase):
    pass


class _Account(_Base):
    __tablename__ = "accounts"

    id:            Mapped[int]  = mapped_column(Integer, primary_key=True, autoincrement=True)
    service:       Mapped[str]  = mapped_column(String(64), nullable=False)
    email:         Mapped[str]  = mapped_column(String(256), nullable=False)
    password:      Mapped[str]  = mapped_column(Text, default="")
    disabled:      Mapped[bool] = mapped_column(Boolean, default=False)
    api_key:       Mapped[str]  = mapped_column(Text, default="")
    credits:       Mapped[int]  = mapped_column(Integer, default=0)
    refresh_token: Mapped[str]  = mapped_column(Text, default="")
    access_token:  Mapped[str]  = mapped_column(Text, default="")
    account_id:    Mapped[str]  = mapped_column(String(256), default="")
    id_token:      Mapped[str]  = mapped_column(Text, default="")
    expired:       Mapped[str]  = mapped_column(String(64), default="")
    last_refresh:  Mapped[str]  = mapped_column(String(64), default="")
    token_type:    Mapped[str]  = mapped_column(String(32), default="")
    created_at:    Mapped[str]  = mapped_column(String(64), nullable=False)
    updated_at:    Mapped[str]  = mapped_column(String(64), nullable=False)
    check_status:  Mapped[str]  = mapped_column(String(32), default="")
    quota_pct:     Mapped[str]  = mapped_column(String(16), default="")
    last_checked:  Mapped[str]  = mapped_column(String(64), default="")
    last_error:    Mapped[str]  = mapped_column(Text, default="")
    session_state: Mapped[str]  = mapped_column(Text, default="")
    totp_secret:   Mapped[str]  = mapped_column(Text, default="")
    app_password:  Mapped[str]  = mapped_column(Text, default="")
    source_email:  Mapped[str]  = mapped_column(Text, default="")
    label:         Mapped[str]  = mapped_column(Text, default="")

    __table_args__ = (
        UniqueConstraint("service", "email", name="uq_service_email"),
        Index("idx_accounts_service", "service"),
        Index("idx_accounts_service_disabled", "service", "disabled"),
    )


class _MailProvider(_Base):
    __tablename__ = "mail_providers"

    id:             Mapped[int]  = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_type:  Mapped[str]  = mapped_column(String(64), nullable=False)
    api_key:        Mapped[str]  = mapped_column(Text, nullable=False, default="")
    server_id:      Mapped[str]  = mapped_column(Text, nullable=False, default="")
    label:          Mapped[str]  = mapped_column(Text, default="")
    disabled:       Mapped[bool] = mapped_column(Boolean, default=False)
    fail_count:     Mapped[int]  = mapped_column(Integer, default=0)
    cooldown_until: Mapped[str]  = mapped_column(String(64), default="")
    last_used:      Mapped[str]  = mapped_column(String(64), default="")
    created_at:     Mapped[str]  = mapped_column(String(64), nullable=False)
    updated_at:     Mapped[str]  = mapped_column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint("provider_type", "api_key", "server_id", name="uq_mail_provider"),
        Index("idx_mail_providers_type", "provider_type"),
        Index("idx_mail_providers_disabled", "disabled"),
    )


class _ProviderDomainTag(_Base):
    __tablename__ = "provider_domain_tags"

    id:            Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_type: Mapped[str] = mapped_column(String(64), nullable=False)
    tag:           Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        UniqueConstraint("provider_type", "tag", name="uq_domain_tag"),
        Index("idx_domain_tag", "tag"),
    )


class _Service(_Base):
    __tablename__ = "services"

    name:          Mapped[str]  = mapped_column(String(64), primary_key=True)
    has_registrar: Mapped[bool] = mapped_column(Boolean, default=False)


class _MailboxServiceBlock(_Base):
    __tablename__ = "mailbox_service_blocks"

    email:      Mapped[str] = mapped_column(String(256), primary_key=True)
    service:    Mapped[str] = mapped_column(String(64),  primary_key=True)
    reason:     Mapped[str] = mapped_column(Text, default="")
    blocked_at: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        Index("idx_msb_service", "service"),
    )


# ── Engine cache ──────────────────────────────────────────────────────────────

_engines: dict[str, Engine] = {}


def _get_engine(db_path: Path) -> Engine:
    key = str(db_path.resolve())
    if key not in _engines:
        engine = create_engine(
            f"sqlite:///{key}",
            connect_args={"check_same_thread": False},
            poolclass=NullPool,
        )

        @event.listens_for(engine, "connect")
        def _set_pragmas(dbapi_conn, _record):
            dbapi_conn.execute("PRAGMA journal_mode=WAL")
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        _engines[key] = engine
    return _engines[key]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def _compute_status(disabled: bool, check_status: str) -> str:
    if disabled or check_status in ("invalid", "error"):
        return "disabled"
    if not check_status:
        return "unchecked"
    return "active"


def _parse_quota_pct(raw: str) -> int | None:
    if not raw:
        return None
    try:
        return int(raw.rstrip("%"))
    except ValueError:
        return None


def _to_dict(row: _Account) -> dict[str, Any]:
    return {
        "id":            row.id,
        "service":       row.service,
        "email":         row.email,
        "password":      row.password,
        "disabled":      row.disabled,
        "status":        _compute_status(row.disabled, row.check_status),
        "api_key":       row.api_key,
        "credits":       row.credits,
        "refresh_token": row.refresh_token,
        "access_token":  row.access_token,
        "account_id":    row.account_id,
        "id_token":      row.id_token,
        "expired":       row.expired,
        "last_refresh":  row.last_refresh,
        "token_type":    row.token_type,
        "created_at":    row.created_at,
        "updated_at":    row.updated_at,
        "check_status":  row.check_status,
        "quota_pct":     _parse_quota_pct(row.quota_pct),
        "last_checked":  row.last_checked,
        "last_error":    row.last_error,
        "session_state": row.session_state,
        "totp_secret":   row.totp_secret,
        "app_password":  row.app_password,
        "source_email":  row.source_email,
    }


def _to_mailbox_dict(row: _Account) -> dict[str, Any]:
    return {
        "email":             row.email,
        "app_password":      row.app_password,
        "totp_secret":       row.totp_secret,
        "password":          row.password,
        "source_email":      row.source_email,
        "google_auth_state": row.session_state,
        "disabled":          row.disabled,
        "label":             row.label,
        "created_at":        row.created_at,
        "updated_at":        row.updated_at,
    }


def _connection_str(provider_type: str, api_key: str, server_id: str) -> str:
    match provider_type:
        case "mailslurp.com":
            return f"mailslurp.com:{api_key}"
        case "testmail.app":
            return f"testmail.app:{server_id}:{api_key}"
        case "mailosaur.com":
            return f"mailosaur.com:{api_key}:{server_id}"
        case "guerrillamail.com":
            return "guerrillamail.com"
        case "mail.tm":
            return server_id or "https://api.mail.tm"
        case "gmail.com":
            return f"gmail.com:{api_key}"
        case _:
            raise ValueError(f"Unknown provider_type: {provider_type!r}")


def _to_provider_dict(row: _MailProvider) -> dict[str, Any]:
    conn = _connection_str(row.provider_type, row.api_key, row.server_id)
    return {
        "id":             row.id,
        "provider_type":  row.provider_type,
        "api_key":        row.api_key,
        "server_id":      row.server_id,
        "connection_str": conn,
        "label":          row.label,
        "disabled":       row.disabled,
        "fail_count":     row.fail_count,
        "cooldown_until": row.cooldown_until,
        "last_used":      row.last_used,
        "created_at":     row.created_at,
        "updated_at":     row.updated_at,
    }


# Whitelist update fields
_UPDATABLE = frozenset({
    "password", "disabled", "api_key", "credits",
    "refresh_token", "access_token", "account_id", "id_token",
    "expired", "last_refresh", "token_type", "updated_at",
    "check_status", "quota_pct", "last_checked", "last_error",
    "session_state", "totp_secret", "app_password", "source_email",
    "label",
})


def _record_to_values(record) -> dict:
    return {
        "service":      record.service.upper(),
        "email":        record.email,
        "password":     record.password,
        "disabled":     record.disabled,
        "api_key":      record.api_key,
        "credits":      record.credits,
        "refresh_token": record.refresh_token,
        "access_token": record.access_token,
        "account_id":   record.account_id,
        "id_token":     record.id_token,
        "expired":      record.expired,
        "last_refresh": record.last_refresh,
        "token_type":   record.token_type,
        "created_at":   record.created_at,
        "updated_at":   record.updated_at,
        "source_email": getattr(record, "source_email", ""),
    }
