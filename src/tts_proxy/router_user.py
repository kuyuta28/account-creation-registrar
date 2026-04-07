"""
router_user.py — User & Subscription info (item 11).

Routes:
  GET /api/user              — thông tin user
  GET /api/user/subscription — chi tiết subscription + quota
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from .errors import RateLimitError
from .key_pool import load_available_keys
from .user_client import get_subscription, get_user

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/user")


def _best_key():
    keys = load_available_keys()
    if not keys:
        raise HTTPException(503, detail="No ElevenLabs keys available")
    return keys[0]


def _handle_errors(exc: Exception) -> None:
    if isinstance(exc, RateLimitError):
        raise HTTPException(429, detail="Rate limited")
    raise HTTPException(502, detail=str(exc))


@router.get("")
async def get_user_endpoint() -> dict:
    """Lấy thông tin user của API key đang dùng.

    Trả về: xi_api_key, first_name, is_onboarded, subscription summary...
    Dùng để verify API key hoạt động không.
    """
    key = _best_key()
    try:
        return await get_user(key.api_key)
    except Exception as exc:  # noqa: BLE001 — HTTP boundary: always re-raises as HTTPException
        _handle_errors(exc)


@router.get("/subscription")
async def get_subscription_endpoint() -> dict:
    """Chi tiết subscription: tier, character_count, character_limit, next_reset...

    character_count: tổng chars đã dùng kỳ này
    character_limit: giới hạn tháng / kỳ
    next_character_count_reset_unix: khi nào reset quota (Unix timestamp)
    status: "active" | "trialing" | "free" | ...
    """
    key = _best_key()
    try:
        return await get_subscription(key.api_key)
    except Exception as exc:  # noqa: BLE001 — HTTP boundary: always re-raises as HTTPException
        _handle_errors(exc)
