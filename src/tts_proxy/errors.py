"""
errors.py — Custom exceptions dùng chung cho tất cả ElevenLabs client modules.
"""
from __future__ import annotations


class ElevenLabsError(Exception):
    """Base error cho tất cả ElevenLabs API calls."""


class RateLimitError(ElevenLabsError):
    """HTTP 429 — key đang bị rate limit, thử key khác."""


class UnusualActivityError(ElevenLabsError):
    """HTTP 401 detected_unusual_activity — free tier bị block, skip key này."""
