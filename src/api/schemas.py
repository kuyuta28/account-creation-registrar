"""
schemas.py — Re-export từ common package.

Giữ file này để backward compat với local imports.
Mọi logic đã chuyển sang common.schemas.
"""
from common.schemas import *  # noqa: F401,F403
from common.schemas import ApiResponse, ErrorDetail, ResponseMeta, err, ok  # noqa: F401
from common.enums import ErrorCode  # noqa: F401 — re-export for backward compat