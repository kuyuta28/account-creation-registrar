"""
providers.py — Router: quản lý mail provider domains + service tags.
Response: unified ApiResponse envelope.
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from ...config.settings import load_config
from ...core.database import (
    get_all_providers_with_tags,
    get_provider_domains,
    set_provider_domain_tags,
    cycle_provider_tag,
    update_provider,
)
from ..exceptions import AppError
from ..schemas import ErrorCode, ok

router = APIRouter(prefix="/providers", tags=["providers"])


def _db_path():
    return load_config().mail.db_path


class SetTagsBody(BaseModel):
    tags: list[str]


class UpdateProviderBody(BaseModel):
    disabled: bool | None = None
    label: str | None = None


@router.get("")
async def list_provider_domains():
    return ok(await asyncio.to_thread(get_provider_domains, _db_path()))


@router.get("/all")
async def list_all_providers():
    return ok(await asyncio.to_thread(get_all_providers_with_tags, _db_path()))


@router.patch("/{provider_id}")
async def patch_provider(provider_id: int, body: UpdateProviderBody):
    fields: dict[str, Any] = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise AppError(ErrorCode.VALIDATION, "No fields to update", 400)
    updated = await asyncio.to_thread(update_provider, _db_path(), provider_id, **fields)
    if not updated:
        raise AppError(ErrorCode.NOT_FOUND, "Provider not found", 404)
    return ok({"updated": True})


@router.put("/{provider_domain}/tags")
async def set_domain_tags(provider_domain: str, body: SetTagsBody):
    count = await asyncio.to_thread(set_provider_domain_tags, _db_path(), provider_domain, body.tags)
    return ok({"updated": count})


@router.post("/{provider_domain}/tag/{service}/cycle")
async def cycle_tag(provider_domain: str, service: str):
    """Cycle tri-state: (empty) → active → blocked → (empty). Trả về tags mới."""
    next_tags = await asyncio.to_thread(cycle_provider_tag, _db_path(), provider_domain, service)
    return ok({"tags": next_tags})
