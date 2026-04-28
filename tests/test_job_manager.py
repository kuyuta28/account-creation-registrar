"""
Tests for JobManager.
"""
import pytest
import asyncio
from api.services.job_manager import JobManager, Job
from common.enums import JobStatus


@pytest.fixture
def mgr():
    return JobManager(max_jobs=10, max_workers=5)


def test_create_job(mgr):
    """Test job creation."""
    job = Job(id="job1", service="ELEVENLABS", count=5, workers=2)
    result = mgr.create_job(job)

    assert result is job
    assert mgr.get_job("job1") is job


def test_max_jobs_enforced(mgr):
    """Test oldest job removed when max reached."""
    for i in range(15):
        job = Job(id=f"job{i}", service="TEST", count=1)
        mgr.create_job(job)

    assert len(mgr._jobs) == 10
    assert mgr.get_job("job0") is None


def test_cancel_job(mgr):
    """Test job cancellation."""
    job = Job(id="job1", service="TEST", count=1)
    mgr.create_job(job)

    assert mgr.request_cancel("job1") is False

    job.status = JobStatus.RUNNING
    assert mgr.request_cancel("job1") is True
    assert mgr.is_cancelled("job1") is True

    mgr.clear_cancel("job1")
    assert mgr.is_cancelled("job1") is False


def test_task_tracking(mgr):
    """Test task reference tracking."""
    async def dummy_task():
        await asyncio.sleep(0.1)

    task = asyncio.create_task(dummy_task())
    mgr.track_task("job1", task)

    assert mgr._tasks.get("job1") is task

    mgr.untrack_task("job1")
    assert "job1" not in mgr._tasks


def test_get_stats(mgr):
    """Test observability metrics."""
    job1 = Job(id="job1", service="ELEVENLABS", count=1)
    job2 = Job(id="job2", service="OPENROUTER", count=1)
    job2.status = JobStatus.RUNNING

    mgr.create_job(job1)
    mgr.create_job(job2)

    stats = mgr.get_stats()
    assert stats["total_jobs"] == 2
    assert stats["active_jobs"] == 1
    assert "jobs_by_status" in stats
    assert "jobs_by_service" in stats


def test_graceful_shutdown(mgr):
    """Test shutdown cancels all tasks."""
    async def long_task():
        await asyncio.sleep(0.1)

    job = Job(id="job1", service="TEST", count=1)
    mgr.create_job(job)
    job.status = JobStatus.RUNNING

    task = asyncio.create_task(long_task())
    mgr.track_task("job1", task)

    asyncio.run(mgr.shutdown())

    assert task.cancelled()
    assert len(mgr._jobs) == 0