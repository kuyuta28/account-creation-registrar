"""
run_api.py - Start FastAPI backend server.
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

import uvicorn

# Thêm zc-zhangchen/any-auto-register vào sys.path để dùng trực tiếp
_zc_path = Path(__file__).parent / "any-auto-register"
if _zc_path.exists():
    sys.path.insert(0, str(_zc_path))

_log = logging.getLogger("app.unhandled")

if sys.platform == "win32":
    # uvicorn 0.30+ gọi asyncio_setup(use_subprocess=True) khi reload=True
    # → set WindowsSelectorEventLoopPolicy → Playwright không spawn subprocess được.
    # Trên Python 3.12, default đã là ProactorEventLoop — patch asyncio_setup thành no-op
    # để giữ ProactorEventLoop cho cả uvicorn reload lẫn Playwright.
    import uvicorn.loops.asyncio as _uvloop
    _uvloop.asyncio_setup = lambda use_subprocess=False: None


def _sync_excepthook(exc_type, exc_value, exc_tb):
    """Global handler cho unhandled sync exceptions — log rồi crash bình thường."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    _log.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def _async_exception_handler(loop: asyncio.AbstractEventLoop, context: dict) -> None:
    """Global handler cho unhandled asyncio Task exceptions."""
    exc = context.get("exception")
    msg = context.get("message", "unknown async error")
    if exc is not None:
        _log.critical("Unhandled async exception: %s", msg, exc_info=exc)
    else:
        _log.critical("Unhandled async error: %s | context=%s", msg, context)


sys.excepthook = _sync_excepthook


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.set_exception_handler(_async_exception_handler)
    asyncio.set_event_loop(loop)

    uvicorn.run(
        "src.api.server:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8709")),
        reload=False,  # set True for development; watch src/ dir for changes
        reload_dirs=["src"],
        loop="none",  # dùng loop ta đã tạo bên trên
    )