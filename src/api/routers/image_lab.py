"""
image_lab.py — Router: Image Lab jobs cho Artificial Analysis.
Response: unified ApiResponse envelope.

Endpoints:
  POST   /image-lab/jobs                 – tạo + start job
  GET    /image-lab/jobs                 – list all jobs
  GET    /image-lab/jobs/{id}            – get job status
  POST   /image-lab/jobs/{id}/cancel     – cancel job
  WS     /image-lab/jobs/{id}/logs       – stream logs
"""
from __future__ import annotations


from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from ..exceptions import AppError
from ..schemas import ErrorCode, ok
from ..services.image_lab_service import (
    ImageLabJob,
    cancel_job,
    create_job,
    get_job,
    list_jobs,
    run_job,
)
from ..ws.log_manager import get_bus, subscribe, unsubscribe

router = APIRouter(prefix="/image-lab", tags=["image-lab"])


class StartImageLabBody(BaseModel):
    prompt: str = Field(..., min_length=1)
    models: list[str] = Field(..., min_length=1)
    aspect_ratio: str = "1:1 (Square)"
    dimensions: str = "1024x1024"
    generations: int = Field(default=1, ge=1, le=10)
    workers: int = Field(default=3, ge=1, le=10)


def _job_dict(job: ImageLabJob) -> dict:
    return {
        "id":                  job.id,
        "prompt":              job.prompt,
        "models":              job.models,
        "aspect_ratio":        job.aspect_ratio,
        "dimensions":          job.dimensions,
        "generations":         job.generations,
        "workers":             job.workers,
        "status":              job.status,
        "created_at":          job.created_at,
        "total_accounts":      job.total_accounts,
        "completed_accounts":  job.completed_accounts,
        "image_paths":         job.image_paths,
        "error":               job.error,
    }


@router.post("/jobs")
async def start_job(body: StartImageLabBody):
    job = create_job(
        prompt=body.prompt,
        models=body.models,
        aspect_ratio=body.aspect_ratio,
        dimensions=body.dimensions,
        generations=body.generations,
        workers=body.workers,
    )
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
