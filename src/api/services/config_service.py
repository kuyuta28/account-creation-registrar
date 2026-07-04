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


# ── Async public API ──────────────────────────────────────────────────────

async def read_config_raw(filename: str = "config.yaml") -> str:
    return await asyncio.to_thread(_read_raw, filename)


async def write_config_raw(content: str, filename: str = "config.yaml") -> None:
    await asyncio.to_thread(_write_raw, content, filename)


async def read_config_dict(filename: str = "config.yaml") -> dict:
    return await asyncio.to_thread(_read_dict, filename)


async def list_config_files() -> list[str]:
    return await asyncio.to_thread(_list_files)
