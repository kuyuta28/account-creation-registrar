"""
mailbox.py — Router: manual temp mailbox management.
Response: unified ApiResponse envelope.

POST /mailbox         → 202 {job_id} — fire-and-forget, không block.
GET  /mailbox/jobs/{id} → poll status (pending|running|done|failed).
"""
from __future__ import annotations


from fastapi import APIRouter, Response
from pydantic import BaseModel

from ..exceptions import AppError
from ..schemas import ErrorCode, ok
from ..services.mailbox_service import (
    fetch_message_detail,
    fetch_messages,
    get_mailbox_job,
    list_active_mailboxes,
    remove_mailbox,
    start_create_mailbox_job,
)

router = APIRouter(prefix="/mailbox", tags=["mailbox"])


class CreateMailboxBody(BaseModel):
    provider: str | None = None


@router.post("")
async def create_mailbox_endpoint(body: CreateMailboxBody, response: Response):
    """Fire-and-forget: tạo job chạy nền, trả 202 + job_id ngay.

    Client poll /mailbox/jobs/{job_id} cho đến khi status='done'|'failed'.
    """
    job_id = start_create_mailbox_job(body.provider)
    response.status_code = 202
    return ok({
        "job_id": job_id,
        "status": "pending",
        "provider": body.provider,
    })


@router.get("/jobs/{job_id}")
async def get_mailbox_job_endpoint(job_id: str):
    job = get_mailbox_job(job_id)
    if job is None:
        raise AppError(ErrorCode.NOT_FOUND, "Job not found or expired", 404)
    return ok(job)


@router.get("")
async def list_mailboxes():
    return ok(list_active_mailboxes())


@router.delete("/{email:path}")
async def delete_mailbox(email: str):
    if not remove_mailbox(email):
        raise AppError(ErrorCode.NOT_FOUND, "Mailbox not found", 404)
    return ok({"deleted": True})


@router.get("/{email:path}/messages")
async def get_messages_endpoint(email: str):
    try:
        result = await fetch_messages(email)
    except KeyError:
        raise AppError(ErrorCode.NOT_FOUND, "Mailbox not found", 404)
    return ok(result)


@router.get("/{email:path}/messages/{message_id}")
async def get_message_detail_endpoint(email: str, message_id: str):
    try:
        result = await fetch_message_detail(email, message_id)
    except KeyError:
        raise AppError(ErrorCode.NOT_FOUND, "Mailbox not found", 404)
    return ok(result)
