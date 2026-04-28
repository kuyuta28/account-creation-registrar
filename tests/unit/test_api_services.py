"""
unit/test_api_services.py — Tests cho src/api/services/registration_service.py

Bao phủ:
  - Job dataclass
  - create_job, get_job, list_jobs, cancel_job
  - make_stream_log_fn
  - _run_worker (async)
"""
from __future__ import annotations

import asyncio
from logging import Logger
from unittest.mock import AsyncMock, MagicMock, patch, call
from common.enums import JobStatus


import pytest


# ── helpers ───────────────────────────────────────────────────────────────────

def _clear_store():
    """Xóa global store + cancel_flags giữa các tests."""
    from src.api.services import registration_service as rs
    rs._store.clear()
    rs._cancel_flags.clear()
    rs._tasks.clear()


# ── Job dataclass ─────────────────────────────────────────────────────────────

class TestJobDataclass:
    def test_default_status_pending(self):
        from src.api.services.registration_service import Job
        job = Job(id="x", service="chatgpt", count=5)
        assert job.status == "pending"

    def test_defaults(self):
        from src.api.services.registration_service import Job
        job = Job(id="x", service="openrouter", count=2)
        assert job.workers == 1
        assert job.created_count == 0
        assert job.processed_count == 0
        assert job.error is None

    def test_created_at_iso_format(self):
        from src.api.services.registration_service import Job
        from datetime import datetime
        job = Job(id="x", service="s", count=1)
        # Phải parse được bằng datetime.fromisoformat
        datetime.fromisoformat(job.created_at)

    def test_id_field_used_literally(self):
        from src.api.services.registration_service import Job
        job = Job(id="test-id-123", service="s", count=1)
        assert job.id == "test-id-123"


# ── create_job ────────────────────────────────────────────────────────────────

class TestCreateJob:
    def setup_method(self):
        _clear_store()

    def test_returns_job_with_correct_fields(self):
        from src.api.services.registration_service import create_job
        job = create_job("chatgpt", 10, workers=3)
        assert job.service == "chatgpt"
        assert job.count == 10
        assert job.workers == 3
        assert job.status == "pending"

    def test_auto_generates_id(self):
        from src.api.services.registration_service import create_job
        j1 = create_job("s", 1)
        j2 = create_job("s", 1)
        assert j1.id != j2.id

    def test_stored_after_creation(self):
        from src.api.services.registration_service import create_job, get_job
        job = create_job("openrouter", 5)
        assert get_job(job.id) is job

    def test_workers_clamped_min_1(self):
        from src.api.services.registration_service import create_job
        job = create_job("s", 1, workers=0)
        assert job.workers == 1

    def test_workers_clamped_max_10(self):
        from src.api.services.registration_service import create_job
        job = create_job("s", 1, workers=20)
        assert job.workers == 10

    def test_evicts_oldest_when_max_jobs_reached(self):
        from src.api.services.registration_service import create_job, get_job
        max_jobs = 5
        with patch("src.api.services.registration_service.load_config",
                   return_value=MagicMock(registration=MagicMock(max_jobs=max_jobs, max_workers=10, max_consecutive_fails=3))):
            first = create_job("s", 1)
            for _ in range(max_jobs - 1):
                create_job("s", 1)
            # Tạo thêm 1 → evict oldest
            create_job("s", 1)
        assert get_job(first.id) is None


# ── get_job ───────────────────────────────────────────────────────────────────

class TestGetJob:
    def setup_method(self):
        _clear_store()

    def test_returns_none_for_unknown_id(self):
        from src.api.services.registration_service import get_job
        assert get_job("nonexistent-id") is None

    def test_returns_job_after_create(self):
        from src.api.services.registration_service import create_job, get_job
        job = create_job("s", 1)
        found = get_job(job.id)
        assert found is job


# ── list_jobs ─────────────────────────────────────────────────────────────────

class TestListJobs:
    def setup_method(self):
        _clear_store()

    def test_empty_initially(self):
        from src.api.services.registration_service import list_jobs
        assert list_jobs() == []

    def test_returns_all_created_jobs(self):
        from src.api.services.registration_service import create_job, list_jobs
        j1 = create_job("s1", 1)
        j2 = create_job("s2", 2)
        jobs = list_jobs()
        assert j1 in jobs
        assert j2 in jobs
        assert len(jobs) == 2

    def test_returns_copy_not_reference(self):
        from src.api.services.registration_service import create_job, list_jobs
        create_job("s", 1)
        lst = list_jobs()
        lst.clear()
        assert len(list_jobs()) == 1


# ── cancel_job ────────────────────────────────────────────────────────────────

class TestCancelJob:
    def setup_method(self):
        _clear_store()

    def test_returns_false_for_unknown_id(self):
        from src.api.services.registration_service import cancel_job
        assert cancel_job("nonexistent") is False

    def test_cancels_pending_job(self):
        from src.api.services.registration_service import create_job, cancel_job, get_job
        job = create_job("s", 1)
        result = cancel_job(job.id)
        assert result is True

    def test_cancel_sets_cancel_flag(self):
        from src.api.services.registration_service import create_job, cancel_job
        from src.api.services import registration_service as rs
        job = create_job("s", 1)
        cancel_job(job.id)
        assert rs._cancel_flags.get(job.id) is True

    def test_cancel_running_job_ok(self):
        from src.api.services.registration_service import create_job, cancel_job
        job = create_job("s", 1)
        job.status = JobStatus.RUNNING
        assert cancel_job(job.id) is True

    def test_cannot_cancel_done_job(self):
        from src.api.services.registration_service import create_job, cancel_job
        job = create_job("s", 1)
        job.status = JobStatus.DONE
        assert cancel_job(job.id) is False

    def test_cannot_cancel_failed_job(self):
        from src.api.services.registration_service import create_job, cancel_job
        job = create_job("s", 1)
        job.status = JobStatus.FAILED
        assert cancel_job(job.id) is False

    def test_cancel_with_task_calls_task_cancel(self):
        from src.api.services.registration_service import create_job, cancel_job
        from src.api.services import registration_service as rs
        job = create_job("s", 1)
        mock_task = MagicMock()
        rs._tasks[job.id] = mock_task
        cancel_job(job.id)
        mock_task.cancel.assert_called_once()


# ── make_stream_log_fn ────────────────────────────────────────────────────────

class TestMakeStreamLogFn:
    def test_signature_accepted(self):
        """make_stream_log_fn(bus, job_id, file_logger) nhận đúng 3 args."""
        from src.api.services.registration_service import make_stream_log_fn
        from src.api.ws.log_manager import LogBus
        bus = LogBus()
        logger = MagicMock(spec=Logger)
        log_fn = make_stream_log_fn(bus, "job-123", logger)
        assert callable(log_fn)

    def test_calling_log_fn_calls_file_logger(self):
        from src.api.services.registration_service import make_stream_log_fn
        from src.api.ws.log_manager import LogBus
        bus = LogBus()
        file_logger = MagicMock()
        log_fn = make_stream_log_fn(bus, "job-1", file_logger)
        with patch("asyncio.ensure_future"), \
             patch("src.api.services.registration_service.broadcast"):
            log_fn("test message")
        assert file_logger.logger.info.call_count == 1
        call_arg = str(file_logger.logger.info.call_args_list[0])
        assert "test message" in call_arg

    def test_each_call_logs_msg(self):
        from src.api.services.registration_service import make_stream_log_fn
        from src.api.ws.log_manager import LogBus
        bus = LogBus()
        file_logger = MagicMock()
        log_fn = make_stream_log_fn(bus, "job-2", file_logger)
        with patch("asyncio.ensure_future"), \
             patch("src.api.services.registration_service.broadcast"):
            log_fn("msg1")
            log_fn("msg2")
        assert file_logger.logger.info.call_count == 2
        call_args = [str(c) for c in file_logger.logger.info.call_args_list]
        assert any("msg1" in c for c in call_args)
        assert any("msg2" in c for c in call_args)


# ── _run_worker ───────────────────────────────────────────────────────────────

class TestRunWorker:
    def setup_method(self):
        _clear_store()

    def test_unknown_service_sets_failed_status(self):
        from src.api.services.registration_service import _run_worker, create_job

        with patch("src.services.registry.make_registrar", return_value=None):
            with patch("src.api.services.aar_client.aar_platforms", new_callable=AsyncMock, return_value={"ELEVENLABS"}):
                with patch("src.api.services.registration_service.load_config",
                       return_value=MagicMock(registration=MagicMock(max_jobs=100, max_workers=10, max_consecutive_fails=3))):
                    job = create_job("unknown_svc", 1)
                    log_fn = MagicMock()
                    save_fn = MagicMock()
                    asyncio.run(_run_worker(job, log_fn, save_fn))

        assert job.status == JobStatus.FAILED
        assert "unknown_svc" in (job.error or "").lower()

    def test_run_worker_is_coroutine(self):
        import inspect
        from src.api.services.registration_service import _run_worker, create_job
        job = create_job("s", 1)
        coro = _run_worker(job, MagicMock(), MagicMock())
        assert inspect.iscoroutine(coro)
        coro.close()  # cleanup


# ── LogBus ────────────────────────────────────────────────────────────────────

class TestLogBus:
    def test_create_empty_bus(self):
        from src.api.ws.log_manager import LogBus
        bus = LogBus()
        assert bus._subscribers == {}
        assert bus.loop is None

    def test_set_event_loop(self):
        from src.api.ws.log_manager import LogBus, set_event_loop
        bus = LogBus()
        loop = asyncio.new_event_loop()
        try:
            set_event_loop(bus, loop)
            assert bus.loop is loop
        finally:
            loop.close()

    def test_subscribe_adds_ws(self):
        from src.api.ws.log_manager import LogBus, subscribe
        bus = LogBus()
        ws = MagicMock()
        asyncio.run(subscribe(bus, "job-1", ws))
        assert ws in bus._subscribers["job-1"]

    def test_unsubscribe_removes_ws(self):
        from src.api.ws.log_manager import LogBus, subscribe, unsubscribe
        bus = LogBus()
        ws = MagicMock()
        asyncio.run(subscribe(bus, "job-1", ws))
        asyncio.run(unsubscribe(bus, "job-1", ws))
        assert ws not in bus._subscribers.get("job-1", set())

    def test_broadcast_calls_send_text(self):
        from src.api.ws.log_manager import LogBus, subscribe, broadcast
        bus = LogBus()
        ws = AsyncMock()
        asyncio.run(subscribe(bus, "job-1", ws))
        asyncio.run(broadcast(bus, "job-1", "hello"))
        ws.send_text.assert_called_once_with("hello")

    def test_broadcast_removes_dead_ws(self):
        from src.api.ws.log_manager import LogBus, subscribe, broadcast
        bus = LogBus()
        ws = AsyncMock()
        ws.send_text.side_effect = Exception("disconnected")
        asyncio.run(subscribe(bus, "job-1", ws))
        asyncio.run(broadcast(bus, "job-1", "msg"))
        # WS bị lỗi → đã bị xóa
        assert ws not in bus._subscribers.get("job-1", set())

    def test_broadcast_to_nonexistent_job_silent(self):
        from src.api.ws.log_manager import LogBus, broadcast
        bus = LogBus()
        # Không raise exception
        asyncio.run(broadcast(bus, "no-job", "msg"))

    def test_cleanup_job_removes_subscribers(self):
        from src.api.ws.log_manager import LogBus, subscribe, cleanup_job
        bus = LogBus()
        ws = AsyncMock()
        asyncio.run(subscribe(bus, "job-1", ws))
        cleanup_job(bus, "job-1")
        assert "job-1" not in bus._subscribers
