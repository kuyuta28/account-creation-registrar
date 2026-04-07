"""
logger.py — Logging utilities.

FP design:
  - LogHandle: frozen dataclass (data)
  - make_logger(): factory tạo LogHandle từ config
  - log_info(), log_error(), log_debug(): pure functions thao tác LogHandle
  - dump_html(), screenshot(): pure side-effect functions
  - make_log_fn(): factory trả LogFn (Callable[[str], None]) với timestamp prefix

_SafeStreamHandler và _TeeStream giữ nguyên là class vì bắt buộc phải implement
Python IO/logging interface — không thể FP hoá.
"""
from __future__ import annotations

import datetime as _dt
import io as _io
import logging
import sys
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock as _Lock
from typing import TYPE_CHECKING
from collections.abc import Callable

if TYPE_CHECKING:
    from ..config.settings import AllLogConfig, LogConfig

LogFn = Callable[[str], None]

# ── Safe console handler (survives Windows code-page encode errors) ───────────
# Phải là class vì kế thừa logging.StreamHandler interface.

class _SafeStreamHandler(logging.StreamHandler):
    def emit(self, record: logging.LogRecord) -> None:
        # Luôn dùng sys.stdout hiện tại để capture TeeStream nếu install_tee() đã chạy.
        # Không dùng self.stream (reference cũ) vì make_logger() có thể được gọi
        # trước khi install_tee() replace sys.stdout.
        self.stream = sys.stdout
        try:
            super().emit(record)
        except UnicodeEncodeError:
            msg = self.format(record)
            enc = getattr(self.stream, "encoding", None) or "utf-8"
            safe = msg.encode(enc, errors="replace").decode(enc)
            self.stream.write(safe + self.terminator)
            self.stream.flush()


# ── Level name → int ──────────────────────────────────────────────────────────

_LEVELS: dict[str, int] = {
    "DEBUG":    logging.DEBUG,
    "INFO":     logging.INFO,
    "WARNING":  logging.WARNING,
    "ERROR":    logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def _lvl(name: str, default: int = logging.DEBUG) -> int:
    return _LEVELS.get(name.upper(), default)


# ── LogHandle: immutable data, operations are module-level functions ───────────

@dataclass(frozen=True)
class LogHandle:
    """
    Immutable handle tới một configured logger + debug dir.
    Dùng make_logger() để tạo, dùng log_info/log_error/log_debug để ghi.
    """
    logger: logging.Logger
    debug_dir: Path


def make_logger(
    name: str,
    log_cfg: LogConfig,
    base_dir: Path,
    log_file_override: Path | None = None,
) -> LogHandle:
    """
    Factory: tạo và cấu hình LogHandle từ config.
    name     — unique logger name, e.g. "main", "worker.0"
    log_cfg  — LogConfig dataclass từ settings.py
    base_dir — project root Path; log file path resolved relative to it
    """
    log_path = log_file_override if log_file_override else base_dir / log_cfg.file.path
    debug_dir = base_dir / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    inner = logging.getLogger(name)
    inner.setLevel(logging.DEBUG)
    inner.handlers.clear()
    inner.propagate = False

    if log_cfg.console.enabled:
        ch = _SafeStreamHandler(sys.stdout)
        ch.setLevel(_lvl(log_cfg.console.level, logging.INFO))
        ch.setFormatter(logging.Formatter(log_cfg.console.format))
        inner.addHandler(ch)

    if log_cfg.file.enabled:
        fh = RotatingFileHandler(
            log_path,
            mode="a" if log_cfg.append else "w",
            encoding="utf-8",
            maxBytes=log_cfg.file.max_bytes,
            backupCount=log_cfg.file.backup_count,
        )
        fh.setLevel(_lvl(log_cfg.file.level, logging.DEBUG))
        fh.setFormatter(logging.Formatter(
            log_cfg.file.format,
            datefmt=log_cfg.file.date_format,
        ))
        inner.addHandler(fh)

    return LogHandle(logger=inner, debug_dir=debug_dir)


# ── Pure logging operations ───────────────────────────────────────────────────

def log_info(handle: LogHandle, msg: str) -> None:
    handle.logger.info(msg)


def log_error(handle: LogHandle, msg: str) -> None:
    handle.logger.error(msg)


def log_debug(handle: LogHandle, msg: str) -> None:
    handle.logger.debug(msg)


def dump_html(handle: LogHandle, content: str, name: str) -> None:
    """Ghi raw HTML string vào debug directory."""
    (handle.debug_dir / name).write_text(content, encoding="utf-8")
    handle.logger.debug("  [HTML] Dumped -> %s/%s", handle.debug_dir.name, name)


def screenshot(handle: LogHandle, data: bytes, name: str, screenshot_dir: Path) -> None:
    """Lưu raw PNG bytes vào screenshots/<name>."""
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    (screenshot_dir / name).write_bytes(data)


# ── LogFn factory ─────────────────────────────────────────────────────────────

_TZ_ICT = _dt.timezone(_dt.timedelta(hours=7))


def make_log_fn(handle: LogHandle) -> LogFn:
    """Lift LogHandle vào plain LogFn với timestamp prefix."""
    def _log(msg: str) -> None:
        ts = _dt.datetime.now(_TZ_ICT).strftime("%H:%M:%S")
        log_info(handle, f"[{ts}] {msg}")
    return _log


# ── Shared "all.log" — tee stdout+stderr vào file ────────────────────────────

_tee_installed = False
_shared_lock = _Lock()


class _TeeStream:
    """Write to both the original stream and a log file."""

    def __init__(self, original: _io.TextIOBase, log_file: _io.TextIOWrapper) -> None:
        self._original = original
        self._log_file = log_file

    def write(self, s: str) -> int:
        try:
            self._original.write(s)
        except Exception:
            pass
        try:
            self._log_file.write(s)
            self._log_file.flush()
        except Exception:
            pass
        return len(s) if s else 0

    def flush(self) -> None:
        try:
            self._original.flush()
        except Exception:
            pass
        try:
            self._log_file.flush()
        except Exception:
            pass

    def fileno(self) -> int:
        return self._original.fileno()

    @property
    def encoding(self) -> str:
        return getattr(self._original, "encoding", "utf-8")

    def isatty(self) -> bool:
        return False

    def writable(self) -> bool:
        return True


def install_tee(base_dir: Path, all_log_cfg: AllLogConfig) -> None:
    """Redirect stdout+stderr so everything also goes to all.log, driven by config."""
    global _tee_installed
    with _shared_lock:
        if _tee_installed:
            return
        if not all_log_cfg.enabled:
            _tee_installed = True
            return
        log_path = base_dir / all_log_cfg.path
        log_path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if all_log_cfg.append else "w"
        fh = open(log_path, mode, encoding="utf-8", errors="replace")
        sys.stdout = _TeeStream(sys.__stdout__, fh)  # type: ignore[assignment]
        sys.stderr = _TeeStream(sys.__stderr__, fh)  # type: ignore[assignment]
        _tee_installed = True
