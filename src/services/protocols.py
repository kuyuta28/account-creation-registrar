"""
protocols.py — Type contracts cho registration pipeline.

FP approach: inject behaviour dưới dạng callable, không dùng object.

  LogFn   = fn nhận một string message
  SaveFn  = fn lưu AccountRecord
  Registrar = callable chạy 1 lần đăng ký, trả về record hoặc None
"""
from __future__ import annotations

from typing import Protocol
from collections.abc import Callable

from src.core.storage import AccountRecord

# ── Primitive callables ────────────────────────────────────────────────
LogFn  = Callable[[str], None]
SaveFn = Callable[[AccountRecord], None]


class Registrar(Protocol):
    """
    Callable contract: chạy 1 lần đăng ký.
    Nhận log_fn + save_fn qua dependency injection.
    """
    async def __call__(
        self,
        log_fn: LogFn,
        save_fn: SaveFn,
    ) -> AccountRecord | None: ...
