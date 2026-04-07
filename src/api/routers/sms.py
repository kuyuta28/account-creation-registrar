"""
sms.py — Router: SMS webhook receiver từ pppscn/SmsForwarder app.

Endpoint chính: POST /sms/webhook
Tương thích với pppscn/SmsForwarder (fields: from, content, sent_time, sim_slot, device_name)

Layer: Router → sms_webhook provider (in-memory queue)
Router không biết gì về DB hay Playwright.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from ..schemas import ok
from ...config.settings import load_config
from ...core.database import delete_sms_phone, get_sms_phones, upsert_sms_phone
from ...core.storage import db_path
from ...mail.providers.sms_webhook import get_messages, make_mailbox, push_sms

router = APIRouter(prefix="/sms", tags=["sms"])
_log = logging.getLogger(__name__)


def _db_path():
    return db_path(load_config().base_dir)


# ── Pydantic models ───────────────────────────────────────────────────────────

class SmsWebhookPayload(BaseModel):
    """
    Payload từ pppscn/SmsForwarder:
      from, content, sent_time (str ms), sim_slot, device_name

    Trường `phone` là số SIM nhận — gửi qua URL query param.
    """
    from_: str | None = None
    content: str | None = None
    sent_time: str | None = None
    sim_slot: str | None = None
    device_name: str | None = None

    model_config = {"populate_by_name": True}

    @classmethod
    def from_raw(cls, data: dict[str, Any]) -> SmsWebhookPayload:
        raw = dict(data)
        if "from" in raw:
            raw["from_"] = raw.pop("from")
        return cls(**{k: v for k, v in raw.items() if k in cls.model_fields})


class UpsertSmsPhoneBody(BaseModel):
    phone: str
    label: str = ""
    disabled: bool = False


class PatchSmsPhoneBody(BaseModel):
    label: str | None = None
    disabled: bool | None = None


@router.get("/phones")
async def list_sms_phones():
    phones = await asyncio.to_thread(get_sms_phones, _db_path())
    return ok(phones)


@router.post("/phones")
async def create_or_update_sms_phone(body: UpsertSmsPhoneBody):
    phone = body.phone.strip()
    if not phone:
        return ok({"created": False, "reason": "missing phone"})
    record = await asyncio.to_thread(upsert_sms_phone, _db_path(), phone, body.label, body.disabled)
    return ok(record)


@router.patch("/phones/{phone}")
async def patch_sms_phone(phone: str, body: PatchSmsPhoneBody):
    current = next(
        (item for item in await asyncio.to_thread(get_sms_phones, _db_path()) if item["phone"] == phone),
        None,
    )
    if not current:
        return ok({"updated": False, "reason": "not found"})
    record = await asyncio.to_thread(
        upsert_sms_phone,
        _db_path(),
        current["phone"],
        current["label"] if body.label is None else body.label,
        current["disabled"] if body.disabled is None else body.disabled,
    )
    return ok(record)


@router.delete("/phones/{phone}")
async def remove_sms_phone(phone: str):
    deleted = await asyncio.to_thread(delete_sms_phone, _db_path(), phone)
    return ok({"deleted": deleted})


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/webhook")
async def sms_webhook(request: Request, phone: str):
    """
    Nhận SMS từ pppscn/SmsForwarder.

    Query param (bắt buộc):
        phone — số điện thoại SIM nhận

    Body: form-urlencoded (mặc định, webParams rỗng) hoặc JSON (webParams tùy chỉnh).

    SmsForwarder mặc định gửi application/x-www-form-urlencoded với:
        from, content, timestamp, sign (nếu có secret)
    Nếu cấu hình webParams JSON thì gửi application/json.
    """
    content_type: str = request.headers.get("content-type", "")
    if "application/json" in content_type:
        raw: dict[str, Any] = await request.json()
    else:
        # form-urlencoded (SmsForwarder default khi webParams rỗng)
        form = await request.form()
        raw = dict(form)
        # map timestamp → sent_time để unify với JSON path
        if "timestamp" in raw and "sent_time" not in raw:
            raw["sent_time"] = raw.pop("timestamp")
    _log.debug("[sms_webhook] raw payload: %s", raw)

    payload = SmsWebhookPayload.from_raw(raw)

    sender = payload.from_ or ""
    if not sender:
        raise ValueError("Missing 'from' field in SmsForwarder payload")

    text = payload.content or ""
    if not text:
        raise ValueError(f"Missing 'content' field in SmsForwarder payload from {sender!r}")

    sent_stamp: int = 0
    if payload.sent_time:
        try:
            sent_stamp = int(payload.sent_time)
        except (ValueError, TypeError):
            sent_stamp = 0

    push_sms(phone_number=phone, from_=sender, text=text, sent_stamp=sent_stamp)

    _log.info("[sms_webhook] SMS received → phone=%s from=%s sim=%s device=%s text=%r",
              phone, sender, payload.sim_slot or "", payload.device_name or "", text[:100])

    return ok({"received": True, "phone": phone, "from": sender})


@router.get("/messages/{phone_number}")
async def list_sms_messages(phone_number: str):
    """Xem SMS đã nhận cho 1 số điện thoại (debug/monitoring)."""
    box = make_mailbox(phone_number)
    msgs = get_messages(box)
    return ok({"phone": phone_number, "count": len(msgs), "messages": msgs})
