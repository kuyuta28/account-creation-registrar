"""
database/_engine.py — ORM models, engine cache, and row serializers.

Internal module — callers use database/__init__.py public API.
"""
from __future__ import annotations

from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Boolean, Engine, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
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
    session_state: Mapped[str]  = mapped_column(Text, default="")
    source_email:  Mapped[str]  = mapped_column(Text, default="")
    check_status:  Mapped[str]  = mapped_column(String(32), default="")
    last_checked:  Mapped[str]  = mapped_column(String(64), default="")
    last_error:    Mapped[str]  = mapped_column(Text, default="")
    created_at:    Mapped[str]  = mapped_column(String(64), nullable=False)
    updated_at:    Mapped[str]  = mapped_column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint("service", "email", name="uq_service_email"),
        Index("idx_accounts_service", "service"),
        Index("idx_accounts_service_disabled", "service", "disabled"),
    )


# ── Extension tables (CTI) ─────────────────────────────────────────────────────

class _AccountGmail(_Base):
    __tablename__ = "accounts_gmail"
    account_id:   Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)
    totp_secret:  Mapped[str] = mapped_column(Text, default="")
    app_password: Mapped[str] = mapped_column(Text, default="")
    label:        Mapped[str] = mapped_column(Text, default="")


class _AccountAA(_Base):
    __tablename__ = "accounts_artificialanalysis"
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)
    api_key:    Mapped[str] = mapped_column(Text, default="")
    org_slug:   Mapped[str] = mapped_column(Text, default="")


class _AccountOpenRouter(_Base):
    __tablename__ = "accounts_openrouter"
    account_id:    Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)
    api_key:       Mapped[str] = mapped_column(Text, default="")
    credits:       Mapped[int] = mapped_column(Integer, default=0)
    quota_pct:     Mapped[str] = mapped_column(String(16), default="")
    refresh_token: Mapped[str] = mapped_column(Text, default="")
    access_token:  Mapped[str] = mapped_column(Text, default="")
    id_token:      Mapped[str] = mapped_column(Text, default="")
    token_type:    Mapped[str] = mapped_column(String(32), default="")
    expired:       Mapped[str] = mapped_column(String(64), default="")
    last_refresh:  Mapped[str] = mapped_column(String(64), default="")


class _AccountTwoSlides(_Base):
    __tablename__ = "accounts_twoslides"
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)
    api_key:    Mapped[str] = mapped_column(Text, default="")
    credits:    Mapped[int] = mapped_column(Integer, default=0)


class _AccountElevenLabs(_Base):
    __tablename__ = "accounts_elevenlabs"
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)
    api_key:    Mapped[str] = mapped_column(Text, default="")


class _AccountOllama(_Base):
    __tablename__ = "accounts_ollama"
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)
    api_key:    Mapped[str] = mapped_column(Text, default="")


class _AccountTestmail(_Base):
    __tablename__ = "accounts_testmail"
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)
    api_key:    Mapped[str] = mapped_column(Text, default="")


class _AccountMailosaur(_Base):
    __tablename__ = "accounts_mailosaur"
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)
    api_key:    Mapped[str] = mapped_column(Text, default="")
    server_id:  Mapped[str] = mapped_column(Text, default="")


# ── CTI registry ───────────────────────────────────────────────────────────────

_EXTENSION_MODELS: dict[str, type] = {
    "GMAIL":              _AccountGmail,
    "ARTIFICIALANALYSIS": _AccountAA,
    "OPENROUTER":         _AccountOpenRouter,
    "2SLIDES":            _AccountTwoSlides,
    "ELEVENLABS":         _AccountElevenLabs,
    "OLLAMA":             _AccountOllama,
    "TESTMAIL":           _AccountTestmail,
    "MAILOSAUR":          _AccountMailosaur,
}

# Fields that live in the base accounts table
_BASE_UPDATABLE = frozenset({
    "password", "disabled", "session_state", "source_email",
    "check_status", "last_checked", "last_error", "updated_at",
})

# Fields that live in each extension table (includes backward-compat aliases)
_EXT_UPDATABLE: dict[str, frozenset[str]] = {
    "GMAIL":              frozenset({"totp_secret", "app_password", "label"}),
    "ARTIFICIALANALYSIS": frozenset({"api_key", "org_slug", "account_id"}),
    "OPENROUTER":         frozenset({"api_key", "credits", "quota_pct", "refresh_token",
                                     "access_token", "id_token", "token_type", "expired", "last_refresh"}),
    "2SLIDES":            frozenset({"api_key", "credits"}),
    "ELEVENLABS":         frozenset({"api_key"}),
    "OLLAMA":             frozenset({"api_key"}),
    "TESTMAIL":           frozenset({"api_key"}),
    "MAILOSAUR":          frozenset({"api_key", "server_id", "account_id"}),
}

# Old flat field name → actual extension column name (backward compat)
_EXT_FIELD_ALIAS: dict[str, dict[str, str]] = {
    "ARTIFICIALANALYSIS": {"account_id": "org_slug"},
    "MAILOSAUR":          {"account_id": "server_id"},
}

# Legacy combined set — kept so old callers importing _UPDATABLE don't break
_UPDATABLE: frozenset[str] = _BASE_UPDATABLE | frozenset({
    "api_key", "credits", "quota_pct", "refresh_token", "access_token",
    "id_token", "token_type", "expired", "last_refresh", "account_id",
    "totp_secret", "app_password", "label",
})


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
    if disabled or check_status == "invalid":
        return "disabled"
    if check_status == "expired":
        return "expired"
    if not check_status or check_status == "error":
        return "unchecked"
    return "active"


def _parse_quota_pct(raw: str) -> int | None:
    if not raw:
        return None
    try:
        return int(raw.rstrip("%"))
    except ValueError:
        return None


def _to_dict(row: _Account, ext=None) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id":            row.id,
        "service":       row.service,
        "email":         row.email,
        "password":      row.password,
        "disabled":      row.disabled,
        "status":        _compute_status(row.disabled, row.check_status),
        "session_state": row.session_state,
        "source_email":  row.source_email,
        "check_status":  row.check_status,
        "last_checked":  row.last_checked,
        "last_error":    row.last_error,
        "created_at":    row.created_at,
        "updated_at":    row.updated_at,
        # backward-compat defaults (populated from extension if present)
        "api_key":       "",
        "credits":       0,
        "quota_pct":     None,
        "refresh_token": "",
        "access_token":  "",
        "id_token":      "",
        "token_type":    "",
        "expired":       "",
        "last_refresh":  "",
        "account_id":    "",
        "totp_secret":   "",
        "app_password":  "",
        "label":         "",
    }
    if ext is None:
        return d
    svc = row.service
    if svc == "GMAIL":
        d["totp_secret"]  = ext.totp_secret
        d["app_password"] = ext.app_password
        d["label"]        = ext.label
    elif svc == "ARTIFICIALANALYSIS":
        d["api_key"]    = ext.api_key
        d["account_id"] = ext.org_slug
    elif svc == "OPENROUTER":
        d["api_key"]       = ext.api_key
        d["credits"]       = ext.credits
        d["quota_pct"]     = _parse_quota_pct(ext.quota_pct)
        d["refresh_token"] = ext.refresh_token
        d["access_token"]  = ext.access_token
        d["id_token"]      = ext.id_token
        d["token_type"]    = ext.token_type
        d["expired"]       = ext.expired
        d["last_refresh"]  = ext.last_refresh
    elif svc == "2SLIDES":
        d["api_key"] = ext.api_key
        d["credits"] = ext.credits
    elif svc in ("ELEVENLABS", "OLLAMA", "TESTMAIL"):
        d["api_key"] = ext.api_key
    elif svc == "MAILOSAUR":
        d["api_key"]    = ext.api_key
        d["account_id"] = ext.server_id
    return d


def _to_mailbox_dict(row: _Account, ext: "_AccountGmail | None" = None) -> dict[str, Any]:
    return {
        "email":             row.email,
        "app_password":      ext.app_password if ext else "",
        "totp_secret":       ext.totp_secret  if ext else "",
        "password":          row.password,
        "source_email":      row.source_email,
        "google_auth_state": row.session_state,
        "disabled":          row.disabled,
        "label":             ext.label if ext else "",
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


def _base_values(record) -> dict:
    """Trả về dict fields cho bảng accounts (base)."""
    return {
        "service":       record.service.upper(),
        "email":         record.email,
        "password":      getattr(record, "password", ""),
        "disabled":      getattr(record, "disabled", False),
        "session_state": getattr(record, "session_state", ""),
        "source_email":  getattr(record, "source_email", ""),
        "created_at":    record.created_at,
        "updated_at":    record.updated_at,
    }


def _ext_values(record) -> dict | None:
    """Trả về dict fields cho extension table tương ứng, hoặc None nếu không có."""
    svc = record.service.upper()
    match svc:
        case "GMAIL":
            return {
                "totp_secret":  getattr(record, "totp_secret", ""),
                "app_password": getattr(record, "app_password", ""),
                "label":        getattr(record, "label", ""),
            }
        case "ARTIFICIALANALYSIS":
            return {
                "api_key":  getattr(record, "api_key", ""),
                "org_slug": getattr(record, "account_id", ""),
            }
        case "OPENROUTER":
            return {
                "api_key":       getattr(record, "api_key", ""),
                "credits":       getattr(record, "credits", 0),
                "quota_pct":     getattr(record, "quota_pct", ""),
                "refresh_token": getattr(record, "refresh_token", ""),
                "access_token":  getattr(record, "access_token", ""),
                "id_token":      getattr(record, "id_token", ""),
                "token_type":    getattr(record, "token_type", ""),
                "expired":       getattr(record, "expired", ""),
                "last_refresh":  getattr(record, "last_refresh", ""),
            }
        case "2SLIDES":
            return {
                "api_key": getattr(record, "api_key", ""),
                "credits": getattr(record, "credits", 0),
            }
        case "ELEVENLABS":
            return {"api_key": getattr(record, "api_key", "")}
        case "OLLAMA":
            return {"api_key": getattr(record, "api_key", "")}
        case "TESTMAIL":
            return {"api_key": getattr(record, "api_key", "")}
        case "MAILOSAUR":
            return {
                "api_key":  getattr(record, "api_key", ""),
                "server_id": getattr(record, "account_id", ""),
            }
        case _:
            return None


# Deprecated — kept for backward compat with any direct callers
def _record_to_values(record) -> dict:
    return _base_values(record)
