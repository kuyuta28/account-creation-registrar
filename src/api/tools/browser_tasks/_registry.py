"""
_registry.py — Task registry cho Browser Gateway.

Handler signature:
    async def handler(*, browser, args, log_fn) -> dict

Gateway:
  1. open_browser(engine, headless, proxy) -> browser
  2. handler(browser=browser, args=args, log_fn=log_fn) -> result
  3. browser.close()
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable

TaskHandler = Callable[..., Awaitable[dict[str, Any]]]

# task_name -> (handler, default_engine)
_REGISTRY: dict[str, tuple[TaskHandler, str]] = {}


def register(task: str, *, engine: str = "camoufox"):
    """Decorator: đăng ký handler cho task. Headless đọc từ cfg.browser.headless."""
    def deco(fn: TaskHandler) -> TaskHandler:
        if task in _REGISTRY:
            raise RuntimeError(f"Task {task!r} đã được đăng ký")
        _REGISTRY[task] = (fn, engine)
        return fn
    return deco


def get_task(task: str) -> tuple[TaskHandler, str] | None:
    return _REGISTRY.get(task)


def list_tasks() -> list[str]:
    return sorted(_REGISTRY)
