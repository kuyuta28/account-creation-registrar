"""
mailbox.py — Router: manual temp mailbox management.
Response: unified ApiResponse envelope.
"""
from __future__ import annotations


from fastapi import APIRouter
from pydantic import BaseModel

from ..exceptions import AppError
from ..schemas import ErrorCode, ok
from ..services.mailbox_service import (
    create_new_mailbox,
    fetch_message_detail,
    fetch_messages,
    list_active_mailboxes,
    remove_mailbox,
)

router = APIRouter(prefix="/mailbox", tags=["mailbox"])


class CreateMailboxBody(BaseModel):
    provider: str | None = None


@router.post("")
async def create_mailbox_endpoint(body: CreateMailboxBody):
    result = await create_new_mailbox(body.provider)
    return ok(result)


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
