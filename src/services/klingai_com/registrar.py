"""services/klingai_com/registrar.py — KlingAI session-save entrypoint.

Lưu Playwright session sau khi user login Google thủ công trên Kling AI.
`save_session` delegate sang gateway task `register_klingai` (headless=False,
visible browser). Gateway chạy `_login_flow` + persist session_state (xem
`flow.py`); container nhận result.

Automation recipe + persistence (`InternalClient`) tách riêng trong `flow.py` —
file này chỉ orchestration.
"""
from __future__ import annotations

from ...config.settings import AppConfig
from common.browser_gateway_client import BrowserGatewayError, run_browser_task
from ..protocols import LogFn
from .flow import AccountRecord


async def save_session(
    cfg: AppConfig,
    log_fn: LogFn,
    repo: object | None = None,
    gmail_hint: str = "",
) -> AccountRecord | None:
    """Mở browser (headless=False qua gateway), đợi user login Google vào Kling AI,
    lưu session vào DB. gmail_hint: nếu biết trước email, truyền vào để định danh.
    """
    gateway_url = cfg.api.host_browser_agent_url
    if not gateway_url:
        raise RuntimeError(
            "HOST_BROWSER_AGENT_URL chưa cấu hình — không thể register KlingAI. "
            "Chạy Browser Gateway trên host (py registrar/tools/host_browser_agent.py)."
        )

    try:
        result = await run_browser_task(
            gateway_url, "register_klingai",
            args={"gmail_hint": gmail_hint},
            headless=False,
            on_log=log_fn,
        )
    except BrowserGatewayError as e:
        raise RuntimeError(f"Gateway register KlingAI thất bại: {e}") from e

    if not result.get("ok"):
        return None

    email = result["email"]
    record = AccountRecord(service="KLINGAI", email=email, password="", api_key="")
    log_fn(f"[OK] Session đã lưu vào DB cho: {email}")
    return record
