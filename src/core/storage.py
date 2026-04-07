"""
storage.py - Repository pattern for account persistence.

The repository coordinates persistence only.
Serialization and service-specific export logic live in pure helper functions so
behavior stays easy to test and extend.

Persistence backend: SQLite (via database.py).
Auth file export (codex auth → auth/*.json) is preserved as-is.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, UTC
from functools import partial
from pathlib import Path
from typing import Any
from collections.abc import Callable

from ..config.settings import AuthSyncConfig, ClipRoxySyncConfig
from .database import (
    delete_account,
    delete_accounts,
    get_account_by_email,
    get_accounts,
    init_db,
    insert_account,
    update_account,
    update_accounts_bulk,
    upsert_account,
)


@dataclass(frozen=True)
class AccountRecord:
    service: str
    email: str
    password: str
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
    totp_secret: str = ""   # Base32 TOTP secret (GMAIL 2FA)
    app_password: str = ""  # Gmail App Password cho IMAP
    source_email: str = ""  # Base Gmail nếu email này là alias (dot/plus/googlemail)
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    )


# Forward-ref: Repo defined below, exporter nhận Repo để access bất kỳ config nào cần.
AccountExporter = Callable[["Repo", AccountRecord], None]


def serialize_account_record(record: AccountRecord, include_timestamps: bool = True) -> dict:
    """Return a JSON-ready dict without the service field."""
    payload: dict = {
        "email": record.email,
        "password": record.password,
        "disabled": record.disabled,
    }
    if record.api_key:
        payload["api_key"] = record.api_key
    if record.credits:
        payload["credits"] = record.credits
    if record.refresh_token:
        payload["refresh_token"] = record.refresh_token
    if record.access_token:
        payload["access_token"] = record.access_token
    if record.account_id:
        payload["account_id"] = record.account_id
    if record.id_token:
        payload["id_token"] = record.id_token
    if record.expired:
        payload["expired"] = record.expired
    if record.last_refresh:
        payload["last_refresh"] = record.last_refresh
    if record.token_type:
        payload["type"] = record.token_type
    if include_timestamps:
        payload["created_at"] = record.created_at
        payload["updated_at"] = record.updated_at
    return payload


def service_accounts_path(base_dir: Path, service: str) -> Path:
    """Legacy path — giữ cho migration script."""
    return base_dir / "data" / f"{service.lower()}_accounts.json"


def db_path(base_dir: Path) -> Path:
    return base_dir / "data" / "accounts.db"


def auth_export_dir(base_dir: Path) -> Path:
    return base_dir / "auth"


def should_export_codex_auth(record: AccountRecord) -> bool:
    return record.service.upper() == "CHATGPT" and record.token_type == "codex"


def build_codex_auth_path(base_dir: Path, email: str) -> Path:
    return auth_export_dir(base_dir) / f"codex-{safe_filename(email)}-free.json"


def build_target_codex_auth_path(target_dir: Path, email: str) -> Path:
    return target_dir / f"codex-{safe_filename(email)}-free.json"


def is_auth_sync_enabled(auth_sync: AuthSyncConfig | None) -> bool:
    return auth_sync is not None and auth_sync.enabled


def export_codex_auth(repo: Repo, record: AccountRecord) -> None:
    """Export codex auth file + sync to target dir."""
    payload = serialize_account_record(record, include_timestamps=False)
    write_json(build_codex_auth_path(repo.base_dir, record.email), payload)
    sync_codex_auth_payload(record.email, payload, repo.auth_sync)


def sync_codex_auth_payload(
    email: str,
    payload: dict,
    auth_sync: AuthSyncConfig | None,
) -> Path | None:
    if not is_auth_sync_enabled(auth_sync) or auth_sync is None:
        return None
    target_path = build_target_codex_auth_path(auth_sync.target_dir, email)
    write_json(target_path, payload)
    return target_path


def sync_auth_file(source_path: Path, target_dir: Path) -> Path | None:
    payload = read_json(source_path, default=None)
    if not isinstance(payload, dict):
        return None
    target_path = target_dir / source_path.name
    write_json(target_path, payload)
    return target_path


def sync_auth_directory(base_dir: Path, target_dir: Path) -> list[Path]:
    source_dir = auth_export_dir(base_dir)
    if not source_dir.exists():
        return []
    return [
        path
        for source_path in sorted(source_dir.glob("*.json"))
        if (path := sync_auth_file(source_path, target_dir)) is not None
    ]


def should_export_openrouter_key(record: AccountRecord) -> bool:
    return (
        record.service.upper() == "OPENROUTER"
        and bool(record.api_key)
        and not record.disabled
    )


def export_openrouter_key(repo: Repo, record: AccountRecord) -> None:
    """Sync single OpenRouter API key vào CLIProxyAPI qua Management REST API."""
    import httpx

    if repo.cliproxy_sync is None:
        return

    base_url = repo.cliproxy_sync.management_url.rstrip("/")
    api_url = f"{base_url}/v0/management/openai-compatibility"
    openrouter_base = "https://openrouter.ai/api/v1"
    headers = {"Authorization": f"Bearer {repo.cliproxy_sync.management_key}"}

    with httpx.Client(timeout=10) as client:
        resp = client.get(api_url, headers=headers)
        resp.raise_for_status()
        compat_list: list = resp.json().get("openai-compatibility") or []

        or_entry = next(
            (e for e in compat_list if str(e.get("base-url", "")).rstrip("/") == openrouter_base),
            None,
        )
        if or_entry is None:
            or_entry = {
                "name": "openrouter",
                "base-url": openrouter_base,
                "api-key-entries": [],
                "models": [],
            }
            compat_list.append(or_entry)

        existing_keys = {
            e["api-key"] for e in (or_entry.get("api-key-entries") or [])
            if isinstance(e, dict) and "api-key" in e
        }

        if record.api_key in existing_keys:
            return  # Key đã có — skip

        or_entry.setdefault("api-key-entries", []).append({"api-key": record.api_key})
        put_resp = client.put(api_url, json=compat_list, headers=headers)
        put_resp.raise_for_status()


def matching_exporters(record: AccountRecord) -> list[AccountExporter]:
    exporters: list[AccountExporter] = []
    if should_export_codex_auth(record):
        exporters.append(export_codex_auth)
    if should_export_openrouter_key(record):
        exporters.append(export_openrouter_key)
    return exporters


# ── Repo: immutable config record ─────────────────────────────────────────────

@dataclass(frozen=True)
class Repo:
    """Immutable bag of storage deps — không phải object với methods."""
    base_dir: Path
    auth_sync: AuthSyncConfig | None = None
    cliproxy_sync: ClipRoxySyncConfig | None = None

    @property
    def db(self) -> Path:
        return db_path(self.base_dir)


# ── Module-level pure functions ────────────────────────────────────────────────

def init_repo(repo: Repo) -> None:
    """Khởi tạo DB (idempotent)."""
    init_db(repo.db)


def repo_save(repo: Repo, record: AccountRecord) -> None:
    """INSERT vào DB + chạy exporters (codex auth, openrouter sync, etc.)."""
    insert_account(repo.db, record)
    for exporter in matching_exporters(record):
        exporter(repo, record)


def make_save_fn(repo: Repo) -> Callable:
    """Partial-apply repo → trả SaveFn."""
    return partial(repo_save, repo)


def repo_all(repo: Repo, service: str) -> list[dict]:
    rows = get_accounts(repo.db, service)
    return [_db_row_to_legacy_dict(r) for r in rows]


def repo_get(repo: Repo, service: str, email: str) -> dict[str, Any] | None:
    row = get_account_by_email(repo.db, service, email)
    return _db_row_to_legacy_dict(row) if row else None


def repo_update(repo: Repo, service: str, email: str, **fields) -> bool:
    return update_account(repo.db, service, email, **fields)


def repo_update_bulk(repo: Repo, service: str, updates: list[dict]) -> int:
    return update_accounts_bulk(repo.db, service, updates)


def repo_delete(repo: Repo, service: str, email: str) -> bool:
    return delete_account(repo.db, service, email)


def repo_delete_many(repo: Repo, service: str, emails: set[str]) -> int:
    return delete_accounts(repo.db, service, emails)


def repo_upsert(repo: Repo, record: AccountRecord) -> None:
    upsert_account(repo.db, record)
    for exporter in matching_exporters(record):
        exporter(repo, record)


def repo_sync_auth(repo: Repo, target_dir: Path | None = None) -> list[Path]:
    if target_dir is not None:
        return sync_auth_directory(repo.base_dir, target_dir)
    if not is_auth_sync_enabled(repo.auth_sync) or repo.auth_sync is None:
        return []
    return sync_auth_directory(repo.base_dir, repo.auth_sync.target_dir)



def _db_row_to_legacy_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Convert DB row dict → legacy JSON-compatible dict (cho backward compat)."""
    d: dict[str, Any] = {
        "email": row["email"],
        "password": row["password"],
        "disabled": row["disabled"],
    }
    if row.get("api_key"):
        d["api_key"] = row["api_key"]
    if row.get("credits"):
        d["credits"] = row["credits"]
    if row.get("refresh_token"):
        d["refresh_token"] = row["refresh_token"]
    if row.get("access_token"):
        d["access_token"] = row["access_token"]
    if row.get("account_id"):
        d["account_id"] = row["account_id"]
    if row.get("id_token"):
        d["id_token"] = row["id_token"]
    if row.get("expired"):
        d["expired"] = row["expired"]
    if row.get("last_refresh"):
        d["last_refresh"] = row["last_refresh"]
    if row.get("token_type"):
        d["type"] = row["token_type"]
    d["created_at"] = row.get("created_at", "")
    d["updated_at"] = row.get("updated_at", "")
    return d


def load_json(path: Path) -> list:
    payload = read_json(path, default=[])
    return payload if isinstance(payload, list) else []


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(_json_text(path))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(payload))


def safe_filename(value: str) -> str:
    return "".join(c if c.isalnum() or c in "@._-" else "_" for c in value)


def _json_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return raw.decode("utf-8")


def _json_bytes(payload: object) -> bytes:
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
