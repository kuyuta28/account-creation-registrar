"""
log_manager.py — LogBus: WebSocket broadcast channel cho live job logs.

FP design:
  - LogBus là dataclass (value object, không phải service object)
  - Tất cả operations là module-level functions nhận LogBus làm tham số đầu tiên
  - make_thread_safe_sender() trả về LogFn dùng được trong background thread
  - Singleton _bus dùng như shared state, inject qua get_bus()

Public API:
  set_event_loop(bus, loop)             — gọi lúc startup
  subscribe(bus, job_id, ws)            — async, thêm subscriber
  unsubscribe(bus, job_id, ws)          — async, xóa subscriber
  broadcast(bus, job_id, message)       — async, gửi tới tất cả subscriber
  make_thread_safe_sender(bus, job_id)  — trả LogFn an toàn cho thread
  cleanup_job(bus, job_id)              — xóa subscribers sau khi job xong
  get_bus()                             — trả singleton bus
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from collections.abc import Callable

from fastapi import WebSocket

LogSendFn = Callable[[str], None]


# ── Data ──────────────────────────────────────────────────────────────

@dataclass
class LogBus:
    """Mutable broadcast bus cho một tập job log streams."""
    _subscribers: dict[str, set[WebSocket]] = field(default_factory=dict)
    loop: asyncio.AbstractEventLoop | None = None


# ── Pure module-level functions ────────────────────────────────────────

def set_event_loop(bus: LogBus, loop: asyncio.AbstractEventLoop) -> None:
    bus.loop = loop


async def subscribe(bus: LogBus, job_id: str, ws: WebSocket) -> None:
    bus._subscribers.setdefault(job_id, set()).add(ws)


async def unsubscribe(bus: LogBus, job_id: str, ws: WebSocket) -> None:
    bus._subscribers.get(job_id, set()).discard(ws)


async def broadcast(bus: LogBus, job_id: str, message: str) -> None:
    dead: set[WebSocket] = set()
    for ws in list(bus._subscribers.get(job_id, set())):
        try:
            await ws.send_text(message)
        except Exception:
            dead.add(ws)
    for ws in dead:
        bus._subscribers.get(job_id, set()).discard(ws)


def make_thread_safe_sender(bus: LogBus, job_id: str) -> LogSendFn:
    """
    Trả về một LogFn thread-safe.
    Dùng cho background thread cần push log lên WebSocket async loop.
    """
    def _send(msg: str) -> None:
        if bus.loop:
            asyncio.run_coroutine_threadsafe(
                broadcast(bus, job_id, msg),
                bus.loop,
            )
    return _send


# ── Cleanup ───────────────────────────────────────────────────────────

def cleanup_job(bus: LogBus, job_id: str) -> None:
    """Xóa subscribers của job đã xong — tránh memory leak."""
    bus._subscribers.pop(job_id, None)


# ── Singleton + dependency getter ─────────────────────────────────────

_bus = LogBus()


def get_bus() -> LogBus:
    """FastAPI dependency / module accessor."""
    return _bus

