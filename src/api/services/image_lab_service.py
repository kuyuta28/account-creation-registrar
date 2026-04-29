"""
image_lab_service.py — Orchestration cho Image Lab jobs.

FP design (mirror registration_service.py):
  - ImageLabJob là dataclass, mutable vì cần update status trong quá trình chạy
  - ImageLabJobManager instance access qua get_app_context()
  - make_stream_log_fn(): factory log fn vừa broadcast WS vừa ghi file
  - run_job(): nhận bus qua DI, không access global state ngoài manager

Public API:
  create_job(prompt, models, aspect_ratio, dimensions, generations, workers) → ImageLabJob
  get_job(job_id)    → Optional[ImageLabJob]
  list_jobs()        → list[ImageLabJob]
  run_job(job_id, bus) → None  (starts background task)
  cancel_job(job_id) → bool
"""
from __future__ import annotations

import asyncio
import traceback
import uuid
from pathlib import Path
from typing import Any

from ...config.settings import load_config
from common.logger import LogHandle, make_logger, log_info
from ...services.artificialanalysis_ai.image_lab import ImageLabParams
from ...services.artificialanalysis_ai.runner import run_multi_account
from ..ws.log_manager import LogBus, broadcast, cleanup_job
from common.enums import JobStatus
from common.context import get_app_context

from .image_lab_job_manager import ImageLabJobManager, ImageLabJob


def _get_job_manager() -> ImageLabJobManager:
    """Get ImageLabJobManager from app context."""
    mgr = get_app_context().image_lab_manager
    if mgr is None:
        raise RuntimeError("ImageLabJobManager not initialized in app context")
    return mgr


def create_job(
    prompt: str,
    models: list[str],
    aspect_ratio: str,
    dimensions: str,
    generations: int = 1,
    workers: int = 3,
) -> ImageLabJob:
    mgr = _get_job_manager()
    job = ImageLabJob(
        id=str(uuid.uuid4()),
        prompt=prompt,
        models=models,
        aspect_ratio=aspect_ratio,
        dimensions=dimensions,
        generations=generations,
        workers=max(1, workers),
    )
    return mgr.create_job(job)


def get_job(job_id: str) -> ImageLabJob | None:
    return _get_job_manager().get_job(job_id)


def list_jobs() -> list[ImageLabJob]:
    return _get_job_manager().list_jobs()


def cancel_job(job_id: str) -> bool:
    return _get_job_manager().request_cancel(job_id)


# ── Log fn factory ────────────────────────────────────────────────────

def make_stream_log_fn(bus: LogBus, job_id: str, file_logger: LogHandle):
    import datetime as _dt
    _TZ_ICT = _dt.timezone(_dt.timedelta(hours=7))

    def _log(msg: str) -> None:
        ts = _dt.datetime.now(_TZ_ICT).strftime("%H:%M:%S")
        stamped = f"[{ts}] {msg}"
        log_info(file_logger, stamped)
        asyncio.ensure_future(broadcast(bus, job_id, stamped))

    return _log


# ── Background task ───────────────────────────────────────────────────

async def _run_task(job: ImageLabJob, bus: LogBus) -> None:
    cfg = load_config()
    log_handle = make_logger(cfg.base_dir / "logs", f"imagelab_{job.id[:8]}")
    log_fn = make_stream_log_fn(bus, job.id, log_handle)
    mgr = _get_job_manager()

    job.status = JobStatus.RUNNING
    log_fn(f"▶ Image Lab job {job.id[:8]} started")
    log_fn(f"  Prompt: {job.prompt[:80]}{'...' if len(job.prompt) > 80 else ''}")
    log_fn(f"  Models: {job.models}")
    log_fn(f"  {job.aspect_ratio} | {job.dimensions} | {job.generations}x gen | {job.workers} workers")

    params = ImageLabParams(
        prompt=job.prompt,
        models=job.models,
        aspect_ratio=job.aspect_ratio,
        dimensions=job.dimensions,
        generations=job.generations,
    )

    try:
        paths: list[Path] = await run_multi_account(
            cfg=cfg,
            params=params,
            workers=job.workers,
            log_fn=log_fn,
        )
        job.image_paths = [str(p) for p in paths]
        job.status = JobStatus.DONE
        log_fn(f"✅ Done — {len(paths)} image(s) total")
    except asyncio.CancelledError:
        job.status = JobStatus.CANCELLED
        log_fn("⛔ Cancelled")
    except Exception as exc:  # noqa: BLE001 - HTTP boundary - log and return None
        job.status = JobStatus.FAILED
        job.error = str(exc)
        log_fn(f"❌ Failed: {exc}")
        log_fn(traceback.format_exc())
    finally:
        mgr.untrack_task(job.id)
        mgr.clear_cancel(job.id)
        cleanup_job(bus, job.id)


def run_job(job_id: str, bus: LogBus) -> None:
    job = _get_job_manager().get_job(job_id)
    if not job:
        raise KeyError(f"Job {job_id} not found")
    task = asyncio.ensure_future(_run_task(job, bus))
    _get_job_manager().track_task(job_id, task)


def get_stats() -> dict[str, Any]:
    """Observability metrics."""
    return _get_job_manager().get_stats()
