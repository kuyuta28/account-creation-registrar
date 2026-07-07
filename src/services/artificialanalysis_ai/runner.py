"""
runner.py — Multi-account Image Lab orchestrator.

Public API:
  run_multi_account(cfg, params, workers, log_fn) → list[Path]

Flow:
  1. Load all ARTIFICIALANALYSIS accounts có session_state từ DB
  2. Chạy parallel với Semaphore(workers) — mỗi account gọi gateway task
     "run_image_lab_one" (host camoufox)
  3. Container decode base64 ảnh từ gateway → ghi ra output_dir
  4. Collect tất cả Path ảnh đã download

Browser automation chạy trên host qua Browser Gateway (container không có camoufox
binary). Container chỉ orchestrate batch + persist ảnh.
"""
from __future__ import annotations

import asyncio
import base64
from datetime import datetime
from pathlib import Path
from collections.abc import Callable

from ...config.settings import AppConfig
from common.browser_gateway_client import BrowserGatewayError, run_browser_task
from common.database._async import get_accounts_async
from common.database._engine import get_async_session
from .image_lab import ImageLabParams, SessionExpiredError

LogFn = Callable[[str], None]

_SERVICE = "ARTIFICIALANALYSIS"


def _make_output_dir(base_dir: Path, email: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_email = email.replace("@", "_at_").replace(".", "_")
    return base_dir / "output" / "artificialanalysis" / safe_email / ts


async def _load_active_accounts() -> list[dict]:
    """Load ARTIFICIALANALYSIS accounts that have a session_state (async Postgres)."""
    async with get_async_session() as session:
        rows = await get_accounts_async(session, _SERVICE)
    return [r for r in rows if not r.get("disabled") and r.get("session_state")]


def _params_to_dict(params: ImageLabParams) -> dict:
    return {
        "prompt": params.prompt,
        "models": list(params.models),
        "aspect_ratio": params.aspect_ratio,
        "dimensions": params.dimensions,
        "generations": params.generations,
    }


async def _run_one_account(
    gateway_url: str,
    account: dict,
    params: ImageLabParams,
    cfg: AppConfig,
    log_fn: LogFn,
) -> list[Path]:
    email = account["email"]
    output_dir = _make_output_dir(cfg.base_dir, email)
    output_dir.mkdir(parents=True, exist_ok=True)

    def _log(msg: str) -> None:
        log_fn(f"[{email}] {msg}")

    _log("Starting...")
    result = await run_browser_task(
        gateway_url, "run_image_lab_one",
        args={"email": email, "params": _params_to_dict(params)},
        on_log=_log,
    )

    paths: list[Path] = []
    for img in result.get("images", []):
        out_path = output_dir / img["name"]
        out_path.write_bytes(base64.b64decode(img["data"]))
        paths.append(out_path)
        _log(f"  Saved: {out_path.name}")

    _log(f"✅ Done — {len(paths)} image(s)")
    return paths


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
    gateway_url = cfg.api.host_browser_agent_url
    if not gateway_url:
        raise RuntimeError(
            "HOST_BROWSER_AGENT_URL chưa cấu hình — không thể chạy Image Lab. "
            "Chạy Browser Gateway trên host (py registrar/tools/host_browser_agent.py)."
        )

    accounts = await _load_active_accounts()

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

    async def _run_with_sem(account: dict) -> None:
        async with sem:
            try:
                paths = await _run_one_account(gateway_url, account, params, cfg, log_fn)
                async with lock:
                    all_paths.extend(paths)
            except BrowserGatewayError as exc:
                log_fn(f"[{account['email']}] ❌ Skip (gateway): {exc}")
            except SessionExpiredError as exc:
                log_fn(f"[{account['email']}] ❌ Skip (session expired): {exc}")
            except Exception as exc:  # noqa: BLE001 - best-effort action - log and continue
                log_fn(f"[{account['email']}] ❌ Skip: {exc}")

    await asyncio.gather(*(_run_with_sem(acc) for acc in accounts))

    log_fn(f"\n✅ Tổng cộng: {len(all_paths)} ảnh từ {len(accounts)} account(s)")
    return all_paths
