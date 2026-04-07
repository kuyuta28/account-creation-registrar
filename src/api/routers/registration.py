"""
registration.py — Router: tạo + theo dõi registration jobs.
Response: unified ApiResponse envelope.
"""
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ..exceptions import AppError
from ..schemas import ErrorCode, ok
from ..services.registration_service import (
    cancel_job,
    create_job,
    get_job,
    list_jobs,
    run_job,
)
from ..ws.log_manager import get_bus, subscribe, unsubscribe
from ...services.registry import SUPPORTED_SERVICES
from ...config.settings import load_config

router = APIRouter(prefix="/registration", tags=["registration"])


class StartJobBody(BaseModel):
    service: str
    count: int = 1
    workers: int = 1


def _job_dict(job) -> dict:
    return {
        "id":              job.id,
        "service":         job.service,
        "count":           job.count,
        "workers":         job.workers,
        "status":          job.status,
        "created_at":      job.created_at,
        "created_count":   job.created_count,
        "processed_count": job.processed_count,
        "error":           job.error,
    }


@router.get("/services")
async def get_services():
    return ok(SUPPORTED_SERVICES)


@router.post("/jobs")
async def start_job(body: StartJobBody):
    if body.service.upper() not in SUPPORTED_SERVICES:
        raise AppError(ErrorCode.UNSUPPORTED, f"Unsupported service: {body.service}", 400)
    cfg = load_config()
    if body.count < 1 or body.count > cfg.registration.max_count:
        raise AppError(ErrorCode.VALIDATION, f"count must be 1-{cfg.registration.max_count}", 400)
    if body.workers < 1 or body.workers > cfg.registration.max_workers:
        raise AppError(ErrorCode.VALIDATION, f"workers must be 1-{cfg.registration.max_workers}", 400)
    job = create_job(body.service.upper(), body.count, body.workers)
    run_job(job.id, get_bus())
    return ok(_job_dict(job))


@router.get("/jobs")
async def get_jobs():
    return ok([_job_dict(j) for j in list_jobs()])


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise AppError(ErrorCode.NOT_FOUND, "Job not found", 404)
    return ok(_job_dict(job))


@router.post("/jobs/{job_id}/cancel")
async def cancel_job_endpoint(job_id: str):
    cancelled = cancel_job(job_id)
    if not cancelled:
        raise AppError(ErrorCode.NOT_FOUND, "Job not found or already finished", 404)
    return ok({"cancelled": True})


@router.websocket("/jobs/{job_id}/logs")
async def job_logs_ws(job_id: str, ws: WebSocket):
    await ws.accept()
    job = get_job(job_id)
    if not job:
        await ws.close(code=4004)
        return
    bus = get_bus()
    await subscribe(bus, job_id, ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await unsubscribe(bus, job_id, ws)
