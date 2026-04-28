"""
registration_service.py — Orchestration cho account registration jobs.

FP design:
  - Job là dataclass (mutable vì cần update status trong quá trình chạy)
  - JobStore là module-level dict + lock, truy cập qua pure functions
  - make_stream_log_fn(): factory trả LogFn dùng trong background thread
  - run_job(): nhận bus qua DI, không access global state ngoài JobStore
  - Registrar được resolve từ registry.py, không hardcode import

Public API:
  create_job(service, count, workers)  → Job
  get_job(job_id)                      → Optional[Job]
  list_jobs()                          → list[Job]
  run_job(job_id, bus)                 → None  (starts background thread)
"""
from __future__ import annotations

import asyncio
import traceback
import uuid
from datetime import datetime
from typing import NamedTuple

from ...config.settings import load_config
from src.core.storage import Repo, init_repo, make_save_fn
from common.logger import LogHandle, make_logger, log_info
from ...services.errors import FatalRegistrationError
from ..ws.log_manager import LogBus, broadcast, cleanup_job
from ...services.protocols import LogFn, SaveFn
from common.enums import JobStatus
from common.context import get_app_context
from .job_manager import Job, JobManager


# ── Worker channel message types (module-level để tránh tạo class trong vòng lặp) ──

class _WorkItem(NamedTuple):
    acct_num: int   # display hint: "attempt #N" fed by dispatcher


class _WorkResult(NamedTuple):
    success:   bool
    skipped:   bool   # True = registrar returned None/False (non-exception)
    worker_id: int
    acct_num:  int
    fatal:     bool = False  # True = lỗi không thể recover, dừng job ngay


# ── JobStore: via JobManager ──────────────────────────────────────────

def _get_job_manager() -> JobManager:
    return get_app_context().job_state


def create_job(service: str, count: int, workers: int = 1) -> Job:
    cfg = load_config()
    max_workers = cfg.registration.max_workers
    job = Job(id=str(uuid.uuid4()), service=service, count=count, workers=max(1, min(max_workers, workers)))
    return _get_job_manager().create_job(job)


def get_job(job_id: str) -> Job | None:
    return _get_job_manager().get_job(job_id)


def list_jobs() -> list[Job]:
    return _get_job_manager().list_jobs()


def cancel_job(job_id: str) -> bool:
    return _get_job_manager().request_cancel(job_id)


# ── LogFn factory cho asyncio task ───────────────────────────────────

def make_stream_log_fn(bus: LogBus, job_id: str, file_logger: LogHandle) -> LogFn:
    """
    Factory: trả LogFn vừa broadcast SSE vừa ghi file, có timestamp prefix.
    """
    import datetime as _dt
    _TZ_ICT = _dt.timezone(_dt.timedelta(hours=7))
    def _log(msg: str) -> None:
        ts = _dt.datetime.now(_TZ_ICT).strftime("%H:%M:%S")
        stamped = f"[{ts}] {msg}"
        log_info(file_logger, stamped)
        asyncio.ensure_future(broadcast(bus, job_id, stamped))
    return _log


# ── OPENROUTER post-job sync ──────────────────────────────────────────

async def _sync_openrouter_post_job(log_fn: LogFn) -> None:
    """Sync keys vừa tạo vào CLIProxy config sau khi OPENROUTER job hoàn thành."""
    from ..services.sync_service import sync_openrouter_to_cliproxy
    sync_result = await sync_openrouter_to_cliproxy()
    log_fn(f"\n🔗 CLIProxy sync: +{sync_result['added']} keys (total: {sync_result['total']})")


# ── Worker: async function chạy trong asyncio task ────────────────────

async def _run_worker(job: Job, log_fn: LogFn, save_fn: SaveFn, mgr: JobManager) -> None:
    """
    Async execution worker — pure function nhận tất cả deps qua argument.
    Parallel execution qua asyncio.gather với Semaphore giới hạn concurrency.
    """
    from ...services.registry import make_registrar

    cfg = load_config()

    # ── Delegate sang any-auto-register nếu service thuộc AAR ────────
    from .aar_client import aar_platforms, run_aar_job
    aar_svc = await aar_platforms()
    if job.service.upper() in aar_svc:
        job.status = JobStatus.RUNNING
        try:
            created = await run_aar_job(
                platform=job.service,
                count=job.count,
                workers=job.workers,
                log_fn=log_fn,
            )
            job.created_count = created
            job.processed_count = job.count
            job.status = JobStatus.DONE
            log_fn(f"\n✅ Done (via any-auto-register): {created}/{job.count}")
        except asyncio.CancelledError:
            job.status = JobStatus.STOPPED
            job.error  = "Người dùng dừng job"
            log_fn("\n🛑 Người dùng dừng job")
            raise
        except Exception as exc:  # noqa: BLE001 — top-level job runner: catch all to update job status
            job.status = JobStatus.FAILED
            job.error  = str(exc)
            log_fn(f"\n❌ AAR Error: {exc}")
        finally:
            mgr.clear_cancel(job.id)
        return

    # Validate service trước khi bắt đầu (local registrar)
    if make_registrar(job.service.upper(), cfg) is None:
        job.status = JobStatus.FAILED
        job.error  = f"Unknown service: {job.service}"
        log_fn(f"❌ Unknown service: {job.service}")
        return

    job.status = JobStatus.RUNNING
    _MAX_CONSECUTIVE_FAILS = cfg.registration.max_consecutive_fails

    # ── Channels (typed, immutable messages) ──────────────────────────
    work_q:   asyncio.Queue[_WorkItem | None] = asyncio.Queue()
    result_q: asyncio.Queue[_WorkResult]      = asyncio.Queue()

    # ── Worker: pure — nhận _WorkItem, trả _WorkResult, không đụng job ─
    async def worker(worker_id: int) -> None:
        w_tag = f"[W{worker_id}]" if job.workers > 1 else ""

        while True:
            item = await work_q.get()
            work_q.task_done()
            if item is None:             # poison pill → dừng
                return

            acct_tag = f"[#{item.acct_num}/{job.count}]"

            def worker_log(msg: str) -> None:
                if not w_tag:
                    log_fn(msg)
                    return
                log_fn("\n".join(
                    f"{w_tag} {line}" if line.strip() else line
                    for line in msg.splitlines()
                ))

            log_fn(f"\n{'─'*48}\n  {acct_tag}{w_tag} Starting...\n{'─'*48}")
            registrar = make_registrar(job.service.upper(), cfg)
            try:
                result = await registrar(log_fn=worker_log, save_fn=save_fn)
                if result:
                    await result_q.put(_WorkResult(
                        success=True, skipped=False,
                        worker_id=worker_id, acct_num=item.acct_num,
                    ))
                else:
                    log_fn(f"  ⚠️ {acct_tag}{w_tag} skipped (no result)")
                    await result_q.put(_WorkResult(
                        success=False, skipped=True,
                        worker_id=worker_id, acct_num=item.acct_num,
                    ))
            except Exception as exc:  # noqa: BLE001 - batch worker: per-item isolation
                log_fn(f"\n❌ {acct_tag}{w_tag} Failed: {exc}\n{traceback.format_exc()}")
                await result_q.put(_WorkResult(
                    success=False, skipped=False,
                    worker_id=worker_id, acct_num=item.acct_num,
                    fatal=isinstance(exc, FatalRegistrationError),
                ))

    # ── Dispatcher: sole owner of all job state transitions ───────────
    async def dispatcher() -> None:
        in_flight         = 0
        consecutive_fails = 0
        created           = 0
        processed         = 0
        next_acct_num     = 1

        def _need_more() -> bool:
            return (
                created + in_flight < job.count
                and not mgr.is_cancelled(job.id)
                and consecutive_fails < _MAX_CONSECUTIVE_FAILS
            )

        async def _enqueue() -> None:
            nonlocal in_flight, next_acct_num
            await work_q.put(_WorkItem(acct_num=next_acct_num))
            next_acct_num += 1
            in_flight     += 1

        # Nạp đủ workers ban đầu
        while in_flight < job.workers and _need_more():
            await _enqueue()

        # Vòng lặp chính — đọc kết quả, nạp task mới ngay lập tức
        while in_flight > 0:
            res        = await result_q.get()
            in_flight -= 1
            processed += 1
            job.processed_count = processed   # ← chỉ dispatcher ghi job

            if res.success:
                created += 1
                job.created_count = created   # ← chỉ dispatcher ghi job
                consecutive_fails = 0
                w_tag = f"[W{res.worker_id}]" if job.workers > 1 else ""
                log_fn(f"  ✅ [{created}/{job.count}]{w_tag} Account created")
            else:
                consecutive_fails += 1

            if res.fatal:
                job.status = JobStatus.STOPPED
                job.error  = "Không còn mailbox khả dụng"
                log_fn("\n🛑 Không còn mailbox khả dụng — dừng job")
                break

            if consecutive_fails >= _MAX_CONSECUTIVE_FAILS:
                job.status = JobStatus.STOPPED
                job.error  = f"{consecutive_fails} lần fail liên tục"
                log_fn(f"\n🛑 {consecutive_fails} lần fail liên tục — dừng job")
                break

            if mgr.is_cancelled(job.id):
                job.status = JobStatus.STOPPED
                job.error  = "Người dùng dừng job"
                log_fn("\n🛑 Người dùng dừng job")
                break

            if _need_more():
                await _enqueue()

        # Gửi poison pill — workers nhận và dừng sạch
        for _ in range(job.workers):
            await work_q.put(None)

    try:
        worker_tasks = [
            asyncio.create_task(worker(i + 1))
            for i in range(job.workers)
        ]
        await dispatcher()
        await asyncio.gather(*worker_tasks, return_exceptions=True)

        if job.status == JobStatus.RUNNING:
            job.status = JobStatus.DONE
            log_fn(f"\n✅ Done: {job.created_count}/{job.count} created (total attempts: {job.processed_count})")

        # Auto-sync OPENROUTER keys vào CLIProxy sau khi job done
        if job.service.upper() == "OPENROUTER" and job.created_count > 0:
            try:
                await _sync_openrouter_post_job(log_fn)
            except Exception as exc:  # noqa: BLE001 - batch worker: per-item isolation
                log_fn(f"\n⚠️ CLIProxy sync failed: {exc}")
    except asyncio.CancelledError:
        job.status = JobStatus.STOPPED
        job.error  = "Người dùng dừng job"
        log_fn("\n🛑 Người dùng dừng job")
        raise
    except Exception as exc:  # noqa: BLE001 - batch worker: per-item isolation
        job.status = JobStatus.FAILED
        job.error  = str(exc)
        log_fn(f"\n❌ Error: {exc}\n{traceback.format_exc()}")
    finally:
        mgr.clear_cancel(job.id)


# ── Public runner ─────────────────────────────────────────────────────

def run_job(job_id: str, bus: LogBus) -> None:
    """
    Khởi động job trong asyncio background task.
    Dependency injection: bus được truyền vào, không dùng singleton trực tiếp.
    """
    job = _get_job_manager().get_job(job_id)
    if not job:
        return

    mgr = _get_job_manager()
    cfg    = load_config()
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = cfg.base_dir / "logs" / f"{job.service.lower()}_{ts}_{job_id[:8]}.log"
    file_logger = make_logger(f"job.{job_id[:8]}", cfg.log, cfg.base_dir, log_file_override=log_file)
    log_fn = make_stream_log_fn(bus, job_id, file_logger)

    repo = Repo(base_dir=cfg.base_dir, auth_sync=cfg.auth_sync, cliproxy_sync=cfg.cliproxy_sync)
    init_repo(repo)
    save_fn: SaveFn = make_save_fn(repo)

    async def _worker_with_cleanup() -> None:
        try:
            await _run_worker(job, log_fn, save_fn, mgr)
        except asyncio.CancelledError:
            if job.status == JobStatus.RUNNING:
                job.status = JobStatus.FAILED
                job.error  = "Task cancelled"
        except Exception as exc:  # noqa: BLE001 - batch worker: per-item isolation
            if job.status == JobStatus.RUNNING:
                job.status = JobStatus.FAILED
                job.error  = str(exc)
        finally:
            mgr.untrack_task(job_id)
            cleanup_job(bus, job_id)

    task = asyncio.create_task(_worker_with_cleanup())
    mgr.track_task(job_id, task)

