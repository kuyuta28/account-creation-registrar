"""
aar_client.py — Async client delegate sang any-auto-register (port 8080).

Platforms được delegate: chatgpt, trae, grok, kiro, openblocklabs
(bất kỳ thứ gì any-auto-register hỗ trợ, tự detect qua /api/platforms)

Public API:
    aar_platforms()           — set[str] tên platform AAR hỗ trợ (uppercase)
    run_aar_job(...)          — chạy job trên AAR, stream log qua log_fn
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import Callable

import httpx

from ...config.settings import load_config


def _aar_cfg():
    """Lazily load AAR config."""
    return load_config().aar


def _aar_base_url():
    return _aar_cfg().base_url


# Cache platform list để không fetch mỗi request
_aar_platforms_cache: set[str] | None = None
_aar_platforms_lock = asyncio.Lock()


async def aar_platforms() -> set[str]:
    """Trả set tên platform (UPPERCASE) mà any-auto-register hỗ trợ."""
    global _aar_platforms_cache
    cfg = _aar_cfg()
    async with _aar_platforms_lock:
        if _aar_platforms_cache is None:
            async with httpx.AsyncClient(timeout=cfg.platforms_timeout_sec) as client:
                r = await client.get(f"{cfg.base_url}/api/platforms")
                r.raise_for_status()
                data = r.json()
                _aar_platforms_cache = {p["name"].upper() for p in data}
    return _aar_platforms_cache


async def run_aar_job(
    *,
    platform: str,
    count: int,
    workers: int = 1,
    log_fn: Callable[[str], None],
    proxy: str | None = None,
    extra: dict | None = None,
) -> int:
    """
    Tạo task trên any-auto-register, stream log về log_fn, trả về số acc tạo được.
    Ném ngoại lệ nếu AAR không response hoặc task failed.
    """
    cfg = _aar_cfg()
    payload: dict = {
        "platform": platform.lower(),
        "count": count,
        "concurrency": workers,
    }
    if proxy:
        payload["proxy"] = proxy
    if extra:
        payload["extra"] = extra

    async with httpx.AsyncClient(timeout=cfg.create_task_timeout_sec) as client:
        r = await client.post(f"{cfg.base_url}/api/tasks", json=payload)
        r.raise_for_status()
        task_id: str = r.json()["task_id"]

    log_fn(f"[AAR] Task created: {task_id} — platform={platform} count={count}")

    # Stream SSE log về log_fn
    created = await _stream_task(task_id, log_fn)
    return created


async def _stream_task(task_id: str, log_fn: Callable[[str], None]) -> int:
    """Stream SSE từ AAR task cho đến khi done/failed/stopped. Trả về created count."""
    cfg = _aar_cfg()
    url = f"{cfg.base_url}/api/tasks/{task_id}/logs/stream"
    since = 0
    created = 0

    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("GET", url, params={"since": since}) as resp:
            resp.raise_for_status()
            async for raw_line in resp.aiter_lines():
                if not raw_line.startswith("data:"):
                    continue
                payload_str = raw_line[5:].strip()
                if not payload_str:
                    continue
                event = json.loads(payload_str)
                if "line" in event:
                    log_fn(event["line"])
                if event.get("done"):
                    final_status = event.get("status", "done")
                    if final_status == "failed":
                        raise RuntimeError(f"AAR task {task_id} failed")
                    if final_status == "stopped":
                        raise RuntimeError(f"AAR task {task_id} stopped by user")
                    break

    # Lấy created count từ snapshot
    async with httpx.AsyncClient(timeout=cfg.snapshot_timeout_sec) as client:
        r = await client.get(f"{cfg.base_url}/api/tasks/{task_id}")
        r.raise_for_status()
        snap = r.json()
        created = snap.get("success_count", 0) or snap.get("created", 0)

    return created


async def cancel_aar_task(task_id: str) -> None:
    cfg = _aar_cfg()
    async with httpx.AsyncClient(timeout=cfg.cancel_timeout_sec) as client:
        await client.post(f"{cfg.base_url}/api/tasks/{task_id}/stop")
