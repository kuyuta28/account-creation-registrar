"""
config.py — Router: đọc/ghi các file trong config/ folder.
Response: unified ApiResponse envelope.
"""
from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ..exceptions import AppError
from ..schemas import ErrorCode, ok
from ..services.config_service import (
    list_config_files,
    read_config_dict,
    read_config_raw,
    write_config_raw,
)

router = APIRouter(prefix="/config", tags=["config"])


class WriteConfigBody(BaseModel):
    content: str


@router.get("/files")
async def get_config_files():
    return ok({"files": await list_config_files()})


@router.get("/raw")
async def get_config_raw(file: str = Query(default="config.yaml")):
    try:
        content = await read_config_raw(file)
    except FileNotFoundError:
        raise AppError(ErrorCode.NOT_FOUND, f"File not found: {file}", 404)
    return ok({"content": content, "file": file})


@router.put("/raw")
async def put_config_raw(body: WriteConfigBody, file: str = Query(default="config.yaml")):
    try:
        await write_config_raw(body.content, file)
    except FileNotFoundError as exc:
        raise AppError(ErrorCode.NOT_FOUND, f"Config file not found: {exc}", 404)
    except ValueError as exc:
        raise AppError(ErrorCode.VALIDATION, f"Invalid YAML: {exc}", 400)
    return ok({"saved": True})


@router.get("")
async def get_config():
    return ok(await read_config_dict())
