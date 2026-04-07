"""
config_service.py — Đọc/ghi config.yaml. Async-safe (file I/O qua to_thread).
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import yaml

_CONFIG_DIR = Path("config")


def _file_path(filename: str = "config.yaml") -> Path:
    return _CONFIG_DIR / filename


# ── Sync helpers (chạy trong thread pool) ─────────────────────────────────

def _read_raw(filename: str) -> str:
    return _file_path(filename).read_text(encoding="utf-8")


def _write_raw(content: str, filename: str) -> None:
    parsed = yaml.safe_load(content)
    if not isinstance(parsed, dict):
        raise ValueError(f"YAML content must be a mapping (dict), got {type(parsed).__name__}")
    _file_path(filename).write_text(content, encoding="utf-8")


def _read_dict(filename: str) -> dict:
    return yaml.safe_load(_file_path(filename).read_text(encoding="utf-8")) or {}


def _list_files() -> list[str]:
    return sorted(p.name for p in _CONFIG_DIR.glob("*.yaml"))


def _add_key(key: str) -> int:
    cfg = _read_dict("mail.yaml")
    keys: list[str] = cfg.get("mail", {}).get("mailslurp_api_keys", [])
    if key in keys:
        return len(keys)
    keys.append(key)
    cfg.setdefault("mail", {})["mailslurp_api_keys"] = keys
    raw = yaml.dump(cfg, default_flow_style=False, allow_unicode=True, sort_keys=False)
    _file_path("mail.yaml").write_text(raw, encoding="utf-8")
    return len(keys)


# ── Async public API ──────────────────────────────────────────────────────

async def read_config_raw(filename: str = "config.yaml") -> str:
    return await asyncio.to_thread(_read_raw, filename)


async def write_config_raw(content: str, filename: str = "config.yaml") -> None:
    await asyncio.to_thread(_write_raw, content, filename)


async def read_config_dict(filename: str = "config.yaml") -> dict:
    return await asyncio.to_thread(_read_dict, filename)


async def list_config_files() -> list[str]:
    return await asyncio.to_thread(_list_files)


async def add_mailslurp_key(key: str) -> int:
    """Append 1 MailSlurp API key vào mail.yaml. Trả về tổng số key sau khi thêm."""
    return await asyncio.to_thread(_add_key, key)
