"""
sync_service.py — Business logic cho sync operations.
Responsibilities:
  - sync_openrouter_to_cliproxy: thêm OR keys từ DB vào CLIProxyAPI qua Management API
  - sync_cliproxy: xóa auth files của CHATGPT accounts disabled/invalid/error
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import httpx

from ...config.settings import load_config
from ...core.database import get_accounts
from ...core.storage import db_path

_log = logging.getLogger(__name__)

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _db_path():
    """Lazy: Đọc db_path từ config mỗi lần gọi — không chạy tại import time."""
    return db_path(load_config().base_dir)


async def sync_openrouter_to_cliproxy() -> dict[str, Any]:
    """Sync OPENROUTER API keys từ DB vào CLIProxyAPI qua Management REST API.
    GET current list → compute diff → PUT merged list.
    """
    cfg = load_config()
    base_url = cfg.cliproxy_sync.management_url.rstrip("/")
    api_url = f"{base_url}/v0/management/openai-compatibility"
    headers = {"Authorization": f"Bearer {cfg.cliproxy_sync.management_key}"}

    all_accs = await asyncio.to_thread(get_accounts, _db_path(), "OPENROUTER", True)
    db_keys = {
        acc["api_key"] for acc in all_accs
        if acc.get("api_key")
        and not acc.get("disabled")
        and acc.get("check_status") not in ("invalid", "error")
    }

    if not db_keys:
        return {"added": 0, "total": 0, "message": "no active OPENROUTER keys in DB"}

    async with httpx.AsyncClient(timeout=10) as client:
        get_resp = await client.get(api_url, headers=headers)
        get_resp.raise_for_status()
        compat_list: list = get_resp.json().get("openai-compatibility") or []

        or_entry = next(
            (e for e in compat_list if str(e.get("base-url", "")).rstrip("/") == _OPENROUTER_BASE_URL),
            None,
        )
        if or_entry is None:
            or_entry = {
                "name": "openrouter",
                "base-url": _OPENROUTER_BASE_URL,
                "api-key-entries": [],
                "models": [],
            }
            compat_list.append(or_entry)

        existing_keys = {
            e["api-key"] for e in (or_entry.get("api-key-entries") or [])
            if isinstance(e, dict) and "api-key" in e
        }

        added_keys = [k for k in sorted(db_keys) if k not in existing_keys]
        for key in added_keys:
            or_entry.setdefault("api-key-entries", []).append({"api-key": key})

        if added_keys:
            put_resp = await client.put(api_url, json=compat_list, headers=headers)
            put_resp.raise_for_status()
            _log.info("sync_openrouter_cliproxy: added %d keys via API", len(added_keys))

    return {
        "added": len(added_keys),
        "total": len(or_entry.get("api-key-entries", [])),
        "keys_added": added_keys,
    }


async def sync_cliproxy() -> dict[str, Any]:
    """Xóa auth files của CHATGPT accounts disabled/invalid/error khỏi CLIProxyAPI auth dir."""
    cfg = load_config()
    target_dir = Path(cfg.auth_sync.target_dir)

    if not target_dir.exists():
        return {"error": f"auth dir not found: {target_dir}"}

    all_accs = await asyncio.to_thread(get_accounts, _db_path(), "CHATGPT", True)
    bad_emails = {
        acc["email"] for acc in all_accs
        if acc.get("disabled") or acc.get("check_status") in ("invalid", "error")
    }

    if not bad_emails:
        return {"deleted": 0, "files": [], "message": "no disabled/invalid accounts"}

    def _do_cleanup() -> list[str]:
        deleted: list[str] = []
        for auth_file in target_dir.glob("codex-*-free.json"):
            name = auth_file.stem
            if name.startswith("codex-") and name.endswith("-free"):
                email = name[6:-5]
                if email in bad_emails:
                    auth_file.unlink()
                    deleted.append(auth_file.name)
                    _log.info("Sync: deleted %s (disabled/invalid)", auth_file.name)
        return deleted

    deleted_files = await asyncio.to_thread(_do_cleanup)
    return {
        "deleted": len(deleted_files),
        "files": deleted_files,
        "bad_count": len(bad_emails),
    }
