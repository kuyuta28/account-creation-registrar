"""
runner.py — Multi-account Image Lab orchestrator.

Public API:
  run_multi_account(cfg, params, workers, log_fn) → list[Path]

Flow:
  1. Load all ARTIFICIALANALYSIS accounts có session_state từ DB
  2. Open 1 browser (camoufox)
  3. Chạy parallel với Semaphore(workers)
  4. Mỗi account: new_context(storage_state) → run_image_lab → save session → close context
  5. Collect tất cả Path ảnh đã download
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from collections.abc import Callable

from ...config.settings import AppConfig
from ...core.browser import open_browser
from ...core.database import get_accounts, init_db
from ...core.storage import db_path
from .image_lab import ImageLabParams, SessionExpiredError, run_image_lab
from .session import save_session

LogFn = Callable[[str], None]

_SERVICE = "ARTIFICIALANALYSIS"


def _make_output_dir(base_dir: Path, email: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_email = email.replace("@", "_at_").replace(".", "_")
    return base_dir / "output" / "artificialanalysis" / safe_email / ts


def _load_active_accounts(db: Path) -> list[dict]:
    init_db(db)
    rows = get_accounts(db, _SERVICE)
    return [r for r in rows if not r.get("disabled") and r.get("session_state")]


async def _run_one_account(
    browser,
    account: dict,
    params: ImageLabParams,
    cfg: AppConfig,
    log_fn: LogFn,
) -> list[Path]:
    email = account["email"]
    state = json.loads(account["session_state"])
    output_dir = _make_output_dir(cfg.base_dir, email)

    def _log(msg: str) -> None:
        log_fn(f"[{email}] {msg}")

    _log("Starting...")
    context = await browser.new_context(storage_state=state)
    try:
        paths = await run_image_lab(
            context=context,
            params=params,
            output_dir=output_dir,
            log_fn=_log,
        )
        await save_session(db_path(cfg.base_dir), email, context)
        _log(f"✅ Done — {len(paths)} image(s)")
        return paths
    except SessionExpiredError as exc:
        _log(f"❌ Session expired: {exc}")
        raise
    finally:
        await context.close()


async def run_multi_account(
    cfg: AppConfig,
    params: ImageLabParams,
    workers: int = 3,
    log_fn: LogFn = print,
) -> list[Path]:
    """
    Chạy Image Lab với tất cả AA accounts có session_state, parallel N workers.
    Trả về tất cả Path ảnh đã download.
    Account lỗi sẽ bị skip (log lỗi), không ảnh hưởng account khác.
    """
    _db = db_path(cfg.base_dir)
    accounts = _load_active_accounts(_db)

    if not accounts:
        raise RuntimeError(
            "Không có account ARTIFICIALANALYSIS nào có session_state trong DB.\n"
            "Hãy chạy registrar trước để tạo account và lấy session."
        )

    log_fn(f"📋 Chạy {len(accounts)} account(s) với {workers} worker(s) song song")
    log_fn(f"   Prompt: {params.prompt[:60]}{'...' if len(params.prompt) > 60 else ''}")
    log_fn(f"   Models: {params.models}")
    log_fn(f"   {params.aspect_ratio} | {params.dimensions} | {params.generations}x gen")

    sem = asyncio.Semaphore(workers)
    all_paths: list[Path] = []
    lock = asyncio.Lock()

    async def _run_with_sem(browser, account: dict) -> None:
        async with sem:
            try:
                paths = await _run_one_account(browser, account, params, cfg, log_fn)
                async with lock:
                    all_paths.extend(paths)
            except Exception as exc:  # noqa: BLE001 - best-effort action - log and continue
                log_fn(f"[{account['email']}] ❌ Skip: {exc}")

    async with open_browser(cfg) as browser:
        await asyncio.gather(*[_run_with_sem(browser, acc) for acc in accounts])

    log_fn(f"\n✅ Tổng cộng: {len(all_paths)} ảnh từ {len(accounts)} account(s)")
    return all_paths
