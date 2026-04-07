"""
user_client.py — ElevenLabs User & Subscription API client.

Chức năng:
  get_user()          — GET /v1/user
  get_subscription()  — GET /v1/user/subscription
"""
from __future__ import annotations

from ._http import api_get


async def get_user(api_key: str) -> dict:
    """Lấy thông tin user (xi_api_key, first_name, subscription...).

    Trả về object chứa: xi_api_key, first_name, is_onboarded,
    subscription (tier, character_count, character_limit, ...)
    """
    return await api_get(api_key, "/v1/user")


async def get_subscription(api_key: str) -> dict:
    """Lấy chi tiết subscription (tier, quota, next_reset...).

    Các field quan trọng:
      tier                — "free" | "starter" | "creator" | "pro" | ...
      character_count     — chars đã dùng trong kỳ hiện tại
      character_limit     — giới hạn chars / kỳ
      next_character_count_reset_unix — Unix timestamp kỳ reset tiếp theo
      status              — "active" | "trialing" | ...
    """
    return await api_get(api_key, "/v1/user/subscription")
