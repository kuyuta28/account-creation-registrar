"""
9router sync service — Tương tự sync_openrouter_to_cliproxy nhưng sync sang 9router db.json
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...config.settings import load_config
from common.database import get_accounts
from src.core.storage import db_path


_log = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _load_9router_db(db_path: Path) -> dict[str, Any]:
    if not db_path.exists():
        return {
            "providerConnections": [],
            "providerNodes": [],
            "proxyPools": [],
            "modelAliases": {},
            "mitmAlias": {},
            "combos": [],
            "apiKeys": [],
            "settings": {},
            "pricing": {}
        }
    with open(db_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_9router_db(db_path: Path, data: dict[str, Any]) -> None:
    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _get_max_priority_for_provider(db_data: dict[str, Any], provider: str) -> int:
    connections = db_data.get("providerConnections", [])
    priorities = [
        conn.get("priority", 0)
        for conn in connections
        if conn.get("provider") == provider
    ]
    return max(priorities) if priorities else 0


def _get_existing_emails(db_data: dict[str, Any], provider: str) -> set[str]:
    connections = db_data.get("providerConnections", [])
    return {
        conn.get("name", "").lower()
        for conn in connections
        if conn.get("provider") == provider and conn.get("name")
    }


def _build_ollama_connection(
    email: str,
    api_key: str,
    priority: int,
    last_used_at: str | None = None,
    consecutive_use_count: int = 0,
    test_status: str | None = None,
    last_error: str | None = None,
    last_error_at: str | None = None,
) -> dict[str, Any]:
    """Build Ollama connection với đầy đủ thông tin."""
    now = _utcnow_iso()
    conn = {
        "id": str(uuid.uuid4()),
        "provider": "ollama",
        "authType": "apikey",
        "name": email,
        "priority": priority,
        "isActive": True,
        "createdAt": now,
        "updatedAt": now,
        "apiKey": api_key,
        "lastUsedAt": last_used_at or now,
        "consecutiveUseCount": consecutive_use_count,
        "testStatus": test_status or "active",
        "lastError": last_error,
        "lastErrorAt": last_error_at,
    }
    # Clean null values
    return {k: v for k, v in conn.items() if v is not None}


async def _get_ollama_accounts(
    account_emails: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Get OLLAMA accounts từ DB."""
    cfg = load_config()
    registrar_db = db_path(cfg.base_dir)

    # Get all OLLAMA accounts
    all_accs = await asyncio.to_thread(get_accounts, registrar_db, "OLLAMA", True)

    if account_emails:
        email_set = {e.lower() for e in account_emails}
        all_accs = [a for a in all_accs if a.get("email", "").lower() in email_set]

    return all_accs


def _get_9router_db_path() -> Path:
    """Lấy path 9router db từ config."""
    cfg = load_config()
    if cfg.cliproxy_sync.ninerouter_db_path:
        return cfg.cliproxy_sync.ninerouter_db_path
    raise ValueError("ninerouter_db_path must be configured in cliproxy_sync")


async def sync_ollama_to_9router(
    account_emails: list[str] | None = None,
) -> dict[str, Any]:
    """Sync OLLAMA API keys từ registrar DB sang 9router db.json."""
    target_db = _get_9router_db_path()

    # Đọc 9router db
    db_data = _load_9router_db(target_db)
    existing_emails = _get_existing_emails(db_data, "ollama")
    max_priority = _get_max_priority_for_provider(db_data, "ollama")

    # Query từ registrar DB
    accounts = await _get_ollama_accounts(account_emails)

    added: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for acc in accounts:
        email = acc.get("email", "")
        api_key = acc.get("api_key", "")

        if not api_key:
            skipped.append({"email": email, "reason": "missing_api_key"})
            continue

        if email.lower() in existing_emails:
            skipped.append({"email": email, "reason": "already_exists"})
            continue

        max_priority += 1
        new_conn = _build_ollama_connection(
            email=email,
            api_key=api_key,
            priority=max_priority,
            last_used_at=acc.get("last_used"),
            consecutive_use_count=acc.get("consecutive_use", 0),
            test_status=acc.get("check_status") or "active",
            last_error=acc.get("last_error"),
            last_error_at=acc.get("last_checked"),
        )
        db_data.setdefault("providerConnections", []).append(new_conn)

        added.append({
            "email": email,
            "priority": max_priority,
            "connection_id": new_conn["id"],
        })

    if added:
        _save_9router_db(target_db, db_data)
        _log.info("sync_ollama_to_9router: added %d accounts", len(added))

    return {
        "db_path": str(target_db),
        "total_local": len(accounts),
        "added_count": len(added),
        "skipped_count": len(skipped),
        "added": added,
        "skipped": skipped,
    }


async def preview_sync_ollama_to_9router(
    account_emails: list[str] | None = None,
) -> dict[str, Any]:
    """Preview — xem trước danh sách sẽ được sync."""
    target_db = _get_9router_db_path()

    _log.info("[DEBUG] Preview - 9router db path: %s", target_db)
    _log.info("[DEBUG] File exists: %s", target_db.exists())

    db_data = _load_9router_db(target_db)
    existing_emails = _get_existing_emails(db_data, "ollama")

    # Query từ registrar DB
    accounts = await _get_ollama_accounts(account_emails)

    items = []
    for acc in accounts:
        email = acc.get("email", "")
        api_key = acc.get("api_key", "")
        exists = email.lower() in existing_emails
        items.append({
            "email": email,
            "api_key": api_key,
            "has_api_key": bool(api_key),
            "exists_in_9router": exists,
            "will_sync": bool(api_key) and not exists,
            # Additional fields
            "last_used": acc.get("last_used"),
            "check_status": acc.get("check_status"),
            "last_error": acc.get("last_error"),
            "consecutive_use": acc.get("consecutive_use", 0),
            "disabled": acc.get("disabled", False),
        })

    return {
        "db_path": str(target_db),
        "total": len(items),
        "new_count": sum(1 for x in items if x["will_sync"]),
        "exists_count": sum(1 for x in items if x["exists_in_9router"]),
        "items": items,
    }
