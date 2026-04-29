"""
Tests for ImageLabJobManager.
"""
import pytest
import asyncio
from src.api.services.image_lab_job_manager import ImageLabJobManager, ImageLabJob
from common.enums import JobStatus


@pytest.fixture
def mgr():
    return ImageLabJobManager(max_jobs=10)


@pytest.fixture
def sample_job():
    return ImageLabJob(
        id="job1",
        prompt="test prompt",
        models=["dalle-3"],
        aspect_ratio="1:1",
        dimensions="1024x1024",
        generations=1,
        workers=2,
    )


def test_create_job(mgr, sample_job):
    """Test job creation."""
    result = mgr.create_job(sample_job)
    assert result is sample_job
    assert mgr.get_job("job1") is sample_job


def test_max_jobs_enforced(mgr):
    """Test oldest job removed when max reached."""
    for i in range(15):
        job = ImageLabJob(
            id=f"job{i}",
            prompt="test",
            models=["dalle-3"],
            aspect_ratio="1:1",
            dimensions="1024x1024",
            generations=1,
            workers=1,
        )
        mgr.create_job(job)

    assert len(mgr._jobs) == 10
    assert mgr.get_job("job0") is None


def test_cancel_job(mgr, sample_job):
    """Test job cancellation."""
    mgr.create_job(sample_job)

    # PENDING jobs can be cancelled (is_active=True)
    assert mgr.request_cancel("job1") is True
    assert mgr.is_cancelled("job1") is True

    mgr.clear_cancel("job1")
    assert mgr.is_cancelled("job1") is False

    # Non-active jobs cannot be cancelled
    sample_job.status = JobStatus.DONE
    assert mgr.request_cancel("job1") is False


def test_task_tracking(mgr):
    """Test task reference tracking."""
    async def dummy_task():
        await asyncio.sleep(0.1)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        task = loop.create_task(dummy_task())
        mgr.track_task("job1", task)

        assert mgr._tasks.get("job1") is task

        mgr.untrack_task("job1")
        assert "job1" not in mgr._tasks
    finally:
        loop.close()


def test_get_stats(mgr, sample_job):
    """Test observability metrics."""
    mgr.create_job(sample_job)
    stats = mgr.get_stats()
    assert stats["total_jobs"] == 1
    assert "jobs_by_status" in stats
    assert "jobs_by_model" in stats


def test_graceful_shutdown(mgr, sample_job):
    """Test shutdown cancels all tasks."""
    async def long_task():
        await asyncio.sleep(0.1)

    mgr.create_job(sample_job)
    sample_job.status = JobStatus.RUNNING

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        task = loop.create_task(long_task())
        mgr.track_task("job1", task)

        loop.run_until_complete(mgr.shutdown())

        assert task.cancelled()
        assert len(mgr._jobs) == 0
    finally:
        loop.close()
