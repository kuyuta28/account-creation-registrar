"""
cli/runners.py - Standalone batch runners used by root-level run_*.py scripts.

Each runner wires config / logger / repo / registrar via make_registrar() (FP).
No OOP registrar classes — all delegation goes through the registry.
"""
from __future__ import annotations

import asyncio
import sys
from dataclasses import replace
from pathlib import Path
from collections.abc import Callable

from ..config.settings import load_config
from common.logger import LogHandle, make_logger, make_log_fn, log_info
from src.core.storage import Repo, init_repo, make_save_fn, repo_sync_auth
from ..services.registry import make_registrar
from ..services.klingai_com.registrar import save_session as kling_save_session

_SEP = "=" * 60
_BAR = "-" * 60


def parse_count_arg(argv: list[str] | None = None, default: int = 1) -> int:
    """Return a positive count parsed from argv[1], or default on invalid input."""
    args = sys.argv if argv is None else argv
    if len(args) < 2:
        return default
    try:
        return max(1, int(args[1]))
    except (TypeError, ValueError):
        return default


def parse_workers_arg(argv: list[str] | None = None, default: int = 1) -> int:
    """Return parallel worker count from --workers / -w flag in argv."""
    args = sys.argv if argv is None else argv
    for i, arg in enumerate(args):
        if arg in ("--workers", "-w") and i + 1 < len(args):
            try:
                return max(1, int(args[i + 1]))
            except (TypeError, ValueError):
                return default
    return default


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_repo(cfg) -> Repo:
    repo = Repo(base_dir=cfg.base_dir, auth_sync=cfg.auth_sync, cliproxy_sync=cfg.cliproxy_sync)
    init_repo(repo)
    return repo


def _worker_logger(cfg, worker_idx: int) -> LogHandle:
    worker_file = replace(cfg.log.file, path=f"debug/worker_{worker_idx}/run.log")
    worker_log_cfg = replace(cfg.log, file=worker_file)
    return make_logger(f"worker.{worker_idx}", worker_log_cfg, cfg.base_dir)


# ── FP sequential runner ───────────────────────────────────────────────────────


async def _run_fp_sequential(
    count: int,
    title: str,
    service: str,
    formatter: Callable,
    cfg=None,
) -> None:
    if cfg is None:
        cfg = load_config()
    repo = _make_repo(cfg)
    log = make_logger("main", cfg.log, cfg.base_dir)
    log_fn = make_log_fn(log)
    save_fn = make_save_fn(repo)
    registrar = make_registrar(service, cfg)
    if registrar is None:
        print(f"ERROR: {service} registrar not found in registry.")
        return

    log_info(log, _SEP)
    log_info(log, f"  {title}  (target: {count})")
    log_info(log, _SEP)

    ok = 0
    for i in range(count):
        if count > 1:
            log_fn(f"\n[{i + 1}/{count}] {'-' * 37}")
        record = await registrar(log_fn=log_fn, save_fn=save_fn)
        if record:
            ok += 1
            formatter(record, ok, count)
        else:
            print(f"\nRegistration failed [{i + 1}/{count}].")
        if i < count - 1:
            log_fn(f"\nPausing {cfg.timeouts.batch_delay_sec}s...")
            await asyncio.sleep(cfg.timeouts.batch_delay_sec)

    print(f"\n{_BAR}\n  Created: {ok}/{count}\n{_BAR}")


# ── FP parallel runner ─────────────────────────────────────────────────────────


async def _run_fp_parallel(
    count: int,
    workers: int,
    title: str,
    service: str,
    formatter: Callable,
    cfg=None,
) -> None:
    if cfg is None:
        cfg = load_config()
    repo = _make_repo(cfg)
    save_fn = make_save_fn(repo)

    print(f"\n{_SEP}")
    print(f"  {title}  (target: {count}, workers: {workers})")
    print(f"{_SEP}")

    sem = asyncio.Semaphore(workers)

    async def run_one(i: int):
        async with sem:
            worker_idx = i % workers
            w_log = _worker_logger(cfg, worker_idx)
            w_log_fn = make_log_fn(w_log)
            reg = make_registrar(service, cfg)
            record = await reg(log_fn=w_log_fn, save_fn=save_fn)
            return i, record

    results = await asyncio.gather(*[run_one(i) for i in range(count)])
    ok = 0
    for i, record in sorted(results, key=lambda x: x[0]):
        if record:
            ok += 1
            formatter(record, ok, count)
        else:
            print(f"\n[task {i + 1}] Registration failed.")

    print(f"\n{_BAR}\n  Created: {ok}/{count}\n{_BAR}")


# ── service runners ────────────────────────────────────────────────────────────


def run_elevenlabs(count: int = 1) -> None:
    def _print(record, ok: int, total: int) -> None:
        print(f"\n{_SEP}\nDONE [{ok}/{total}]\n{_SEP}")
        print(f"  Email:    {record.email}")
        print(f"  Password: {record.password}")
        print(f"  API Key:  {record.api_key}")
        print(_SEP)

    asyncio.run(_run_fp_sequential(count, "ElevenLabs Account Creator", "ELEVENLABS", _print))


def run_leonardo(count: int = 1) -> None:
    def _print(record, ok: int, total: int) -> None:
        print(f"\n{_SEP}\nDONE [{ok}/{total}]\n{_SEP}")
        print(f"  Email:    {record.email}")
        print(f"  Password: {record.password}")
        print(_SEP)

    asyncio.run(_run_fp_sequential(count, "Leonardo AI Account Creator", "LEONARDO", _print))


def run_proton(count: int = 1) -> None:
    def _print(record, ok: int, total: int) -> None:
        print(f"\n{_SEP}\nDONE [{ok}/{total}]\n{_SEP}")
        print(f"  Email:    {record.email}")
        print(f"  Password: {record.password}")
        print(_SEP)

    asyncio.run(_run_fp_sequential(count, "Proton Mail Account Creator", "PROTON", _print))


def run_openrouter(count: int = 1, workers: int = 1) -> None:
    def _print(record, ok: int, total: int) -> None:
        print(f"\n{_SEP}\nDONE [{ok}/{total}]\n{_SEP}")
        print(f"  Email:    {record.email}")
        print(f"  Password: {record.password}")
        print(_SEP)

    if workers > 1:
        asyncio.run(_run_fp_parallel(count, workers, "OpenRouter Account Creator", "OPENROUTER", _print))
    else:
        asyncio.run(_run_fp_sequential(count, "OpenRouter Account Creator", "OPENROUTER", _print))


def run_mailosaur(count: int = 1, workers: int = 1) -> None:
    def _print(record, ok: int, total: int) -> None:
        print(f"\n{_SEP}\nDONE [{ok}/{total}]\n{_SEP}")
        print(f"  Email:    {record.email}")
        print(f"  API key:  {record.api_key[:50]}...")
        print(_SEP)

    if workers > 1:
        asyncio.run(_run_fp_parallel(count, workers, "Mailosaur Account Creator", "MAILOSAUR", _print))
    else:
        asyncio.run(_run_fp_sequential(count, "Mailosaur Account Creator", "MAILOSAUR", _print))


def run_auth_sync(target_dir: str | None = None) -> None:
    cfg = load_config()
    repo = _make_repo(cfg)
    destination = Path(target_dir) if target_dir else cfg.auth_sync.target_dir
    synced = repo_sync_auth(repo, destination)
    print(f"\n{_BAR}\n  Synced: {len(synced)} file(s)\n  Target:  {destination}\n{_BAR}")


def run_kling_session(gmail: str = "") -> None:
    """Mở browser, đợi user login Google vào Kling AI, lưu session cookies."""
    cfg = load_config()
    log = make_logger("main", cfg.log, cfg.base_dir)
    repo = _make_repo(cfg)

    print(f"\n{_SEP}")
    print("  Kling AI — Lưu session Google")
    print(_SEP)

    record = asyncio.run(kling_save_session(cfg, make_log_fn(log), repo, gmail_hint=gmail))

    print(f"\n{_BAR}")
    if record:
        print("  DONE")
        print(f"  Email:        {record.email}")
        print(f"  Session file: {record.api_key}")
    else:
        print("  FAILED — Session không được lưu.")
    print(_BAR)


# ── entrypoints ───────────────────────────────────────────────────────────────


def main_run_elevenlabs() -> None:
    run_elevenlabs(parse_count_arg())



def main_run_leonardo() -> None:
    run_leonardo(parse_count_arg())


def main_run_openrouter() -> None:
    run_openrouter(parse_count_arg(), parse_workers_arg())


def main_run_kling_session() -> None:
    gmail = sys.argv[1] if len(sys.argv) > 1 else ""
    run_kling_session(gmail)
