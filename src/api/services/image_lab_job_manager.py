"""
image_lab_job_manager.py — Structured state manager for ImageLab jobs.

Replaces module-level _store, _cancel_flags, _tasks in image_lab_service.py.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any

from common.enums import JobStatus


@dataclass
class ImageLabJob:
    """Job dataclass — mutable state within ImageLabJobManager."""
    id: str
    prompt: str
    models: list[str]
    aspect_ratio: str
    dimensions: str
    generations: int
    workers: int
    status: JobStatus = JobStatus.PENDING
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    total_accounts: int = 0
    completed_accounts: int = 0
    image_paths: list[str] = field(default_factory=list)
    error: str | None = None


class ImageLabJobManager:
    def __init__(self, max_jobs: int = 100) -> None:
        self._max_jobs = max_jobs
        self._jobs: dict[str, ImageLabJob] = {}
        self._cancel_flags: dict[str, bool] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    async def init(self) -> None:
        pass

    async def shutdown(self) -> None:
        for task in self._tasks.values():
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._jobs.clear()
        self._cancel_flags.clear()
        self._tasks.clear()

    def create_job(self, job: ImageLabJob) -> ImageLabJob:
        if len(self._jobs) >= self._max_jobs:
            oldest = next(iter(self._jobs))
            del self._jobs[oldest]
        self._jobs[job.id] = job
        return job

    def get_job(self, job_id: str) -> ImageLabJob | None:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[ImageLabJob]:
        return list(self._jobs.values())

    def request_cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job or not job.status.is_active:
            return False
        self._cancel_flags[job_id] = True
        task = self._tasks.get(job_id)
        if task:
            task.cancel()
        return True

    def is_cancelled(self, job_id: str) -> bool:
        return self._cancel_flags.get(job_id, False)

    def clear_cancel(self, job_id: str) -> None:
        self._cancel_flags.pop(job_id, None)

    def track_task(self, job_id: str, task: asyncio.Task) -> None:
        self._tasks[job_id] = task

    def untrack_task(self, job_id: str) -> None:
        self._tasks.pop(job_id, None)

    def get_stats(self) -> dict[str, Any]:
        jobs = list(self._jobs.values())
        by_status: dict[str, int] = {}
        for j in jobs:
            status_name = j.status.name
            by_status[status_name] = by_status.get(status_name, 0) + 1
        by_model: dict[str, int] = {}
        for j in jobs:
            for model in j.models:
                by_model[model] = by_model.get(model, 0) + 1
        return {
            "total_jobs": len(jobs),
            "active_jobs": sum(1 for j in jobs if j.status.is_active),
            "running_tasks": len(self._tasks),
            "jobs_by_status": by_status,
            "jobs_by_model": by_model,
        }

    def reset(self) -> None:
        self._jobs.clear()
        self._cancel_flags.clear()
        self._tasks.clear()
