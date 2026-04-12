"""
schemas.py — Unified API response envelope.

Mọi endpoint đều trả về ApiResponse[T].

Success (HTTP 2xx):
  {
    "success": true,
    "data": {...} | [...] | null,
    "meta": {"request_id": "uuid4", "ts": "ISO8601"}
  }

Error (HTTP 4xx/5xx):
  {
    "success": false,
    "error": {"code": "NOT_FOUND", "message": "..."},
    "meta": {"request_id": "uuid4", "ts": "ISO8601"}
  }
"""
from __future__ import annotations

import uuid
from datetime import datetime, UTC
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from common.enums import ErrorCode  # noqa: F401 — re-export for backward compat

T = TypeVar("T")


# ── Response shapes ───────────────────────────────────────────────────────────

class ResponseMeta(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ts: str = Field(
        default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    )


class ErrorDetail(BaseModel):
    code: str
    message: str


class ApiResponse(BaseModel, Generic[T]):
    success: bool
    data: T | None = None
    error: ErrorDetail | None = None
    meta: ResponseMeta = Field(default_factory=ResponseMeta)


# ── Factory helpers — dùng trong routers ─────────────────────────────────────

def ok(data: T) -> ApiResponse[T]:
    return ApiResponse(success=True, data=data)


def err(code: str, message: str) -> ApiResponse:
    return ApiResponse(success=False, error=ErrorDetail(code=code, message=message))
