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
from common.database._async import (
    cycle_provider_tag_async,
    get_all_providers_with_tags_async,
    get_provider_domains_async,
    set_provider_domain_tags_async,
    update_provider_async,
)
from common.database._engine import get_async_session
from ..exceptions import AppError
from ..schemas import ErrorCode, ok

router = APIRouter(prefix="/providers", tags=["providers"])


class SetTagsBody(BaseModel):
    tags: list[str]


class UpdateProviderBody(BaseModel):
    disabled: bool | None = None
    label: str | None = None


@router.get("")
async def list_provider_domains():
    async with get_async_session() as session:
        return ok(await get_provider_domains_async(session))


@router.get("/all")
async def list_all_providers():
    async with get_async_session() as session:
        return ok(await get_all_providers_with_tags_async(session))


@router.patch("/{provider_id}")
async def patch_provider(provider_id: int, body: UpdateProviderBody):
    fields: dict[str, Any] = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise AppError(ErrorCode.VALIDATION, "No fields to update", 400)
    async with get_async_session() as session:
        updated = await update_provider_async(session, provider_id, **fields)
    if not updated:
        raise AppError(ErrorCode.NOT_FOUND, "Provider not found", 404)
    return ok({"updated": True})


@router.put("/{provider_domain}/tags")
async def set_domain_tags(provider_domain: str, body: SetTagsBody):
    async with get_async_session() as session:
        count = await set_provider_domain_tags_async(session, provider_domain, body.tags)
    return ok({"updated": count})


@router.post("/{provider_domain}/tag/{service}/cycle")
async def cycle_tag(provider_domain: str, service: str):
    """Cycle tri-state: (empty) → active → blocked → (empty). Trả về tags mới."""
    async with get_async_session() as session:
        next_tags = await cycle_provider_tag_async(session, provider_domain, service)
    return ok({"tags": next_tags})
