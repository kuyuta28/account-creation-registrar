"""
exceptions.py — AppError exception + FastAPI exception handlers.

Mọi lỗi business logic ném AppError → handler convert thành ApiResponse envelope.
"""
from __future__ import annotations

import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .schemas import ErrorCode, err

_LOG = logging.getLogger("app.api")


class AppError(Exception):
    """Business logic error — ném ở bất kỳ tầng nào, handler sẽ bắt."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


# ── HTTP code → ErrorCode mapping ────────────────────────────────────────────

_HTTP_TO_CODE: dict[int, str] = {
    400: ErrorCode.VALIDATION,
    404: ErrorCode.NOT_FOUND,
    409: ErrorCode.CONFLICT,
    422: ErrorCode.VALIDATION,
    500: ErrorCode.INTERNAL,
}


# ── Handlers ─────────────────────────────────────────────────────────────────

async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=err(exc.code, exc.message).model_dump(),
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Flatten lỗi thành message dễ đọc
    first = exc.errors()[0] if exc.errors() else {}
    field = " → ".join(str(x) for x in first.get("loc", []))
    msg = f"{field}: {first.get('msg', 'invalid')}" if field else str(first.get("msg", "invalid input"))
    return JSONResponse(
        status_code=422,
        content=err(ErrorCode.VALIDATION, msg).model_dump(),
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    code = _HTTP_TO_CODE.get(exc.status_code, ErrorCode.INTERNAL)
    return JSONResponse(
        status_code=exc.status_code,
        content=err(code, str(exc.detail)).model_dump(),
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    _LOG.exception(
        "Unhandled exception: %s %s → %s",
        request.method,
        request.url.path,
        exc,
    )
    return JSONResponse(
        status_code=500,
        content=err(ErrorCode.INTERNAL, str(exc)).model_dump(),
    )
