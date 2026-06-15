"""account_record.py — PostgreSQL-only account DTOs.

Module này chỉ giữ shape dữ liệu chung cho registrar runtime. Không chứa SQLite,
không init DB, không fallback filesystem.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from collections.abc import Callable


@dataclass(frozen=True)
class AccountRecord:
    service: str
    email: str
    password: str = ""
    disabled: bool = False
    api_key: str = ""
    credits: int = 0
    refresh_token: str = ""
    access_token: str = ""
    account_id: str = ""
    id_token: str = ""
    expired: str = ""
    last_refresh: str = ""
    token_type: str = ""
    totp_secret: str = ""
    app_password: str = ""
    source_email: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"))
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"))


@dataclass(frozen=True)
class Repo:
    """Config carrier cho CLI flows; DB writes đi qua async PostgreSQL."""

    base_dir: Path
    auth_sync: Any | None = None
    cliproxy_sync: Any | None = None


AccountExporter = Callable[[Repo, AccountRecord], None]


def init_repo(repo: Repo) -> None:
    return None


def make_save_fn(repo: Repo) -> Callable[[AccountRecord], None]:
    def _unsupported_save(_record: AccountRecord) -> None:
        raise RuntimeError("Direct Repo save is removed; use async PostgreSQL account services")

    return _unsupported_save


def repo_sync_auth(repo: Repo, target_dir: Path | None = None) -> list[Path]:
    return []


# Codex / ChatGPT auth sync helpers. CLI flows dùng để mirror refreshed
# tokens giữa local auth/ và cliproxy sync target.

def build_codex_auth_path(base_dir: Path, email: str) -> Path:
    safe = email.replace("@", "_at_").replace("/", "_")
    return base_dir / "auth" / f"codex_{safe}.json"


def serialize_account_record(record: AccountRecord, *, include_timestamps: bool = True) -> dict:
    payload: dict[str, Any] = {
        "email": record.email,
        "access_token": record.access_token,
        "refresh_token": record.refresh_token,
        "id_token": record.id_token,
        "account_id": record.account_id,
        "expired": record.expired,
        "last_refresh": record.last_refresh,
        "token_type": record.token_type,
    }
    if include_timestamps:
        payload["created_at"] = record.created_at
        payload["updated_at"] = record.updated_at
    return payload


def should_export_codex_auth(record: AccountRecord) -> bool:
    return bool(record.refresh_token)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def sync_codex_auth_payload(email: str, payload: dict, auth_sync: Any) -> None:
    if auth_sync is None or not getattr(auth_sync, "enabled", False):
        return
    target_dir = getattr(auth_sync, "target_dir", None)
    if target_dir is None:
        return
    safe = email.replace("@", "_at_").replace("/", "_")
    target_path = Path(target_dir) / f"codex_{safe}.json"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
