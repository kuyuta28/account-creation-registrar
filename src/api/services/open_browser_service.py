"""
open_browser_service.py - Route mo browser thuc (co cua so) qua host-browser-agent.

Registrar chay native tren host; Camoufox voi headless=False chay truc tiep.
Tuy nhien, neu can delegate viee mo browser cua so cho agent rieng,
chung ta dung host-browser-agent - mot daemon nho chay tren cung host.

Flow:
  1. Frontend goi POST /api/v1/gmail/mailboxes/{email}/open-browser
     hoac POST /api/v1/accounts/open-browser.
  2. Router validate account/mailbox co session_state.
  3. Router goi open_browser_window() voi HOST_BROWSER_AGENT_URL tu config.
  4. Helper POST JSON toi http://<agent>/open voi {service, email, url?}.
  5. Agent tren host spawn python -m src.api.tools.open_browser_session,
     chay headless=False, mo cua so that tren desktop.

Khong co fallback ve subprocess local. Neu HOST_BROWSER_AGENT_URL chua cau hinh,
endpoint tra loi ro rang de nguoi dung biet can chay agent tren host.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from ..exceptions import AppError
from ..schemas import ErrorCode

_log = logging.getLogger(__name__)


async def open_browser_window(
    service: str,
    email: str,
    agent_url: str,
    url: str | None = None,
) -> dict[str, Any]:
    """Forward open-browser request toi host-browser-agent.

    Args:
        service: Ten service viet hoa (VD: "GMAIL", "ELEVENLABS").
        email: Email account/mailbox.
        agent_url: Base URL cua host-browser-agent
            (VD: "http://127.0.0.1:9999").
        url: URL mo khi browser khoi dong (optional).

    Returns:
        {"launched": bool, "pid": int | None}

    Raises:
        AppError: Neu agent_url trong hoac agent tra loi loi.
    """
    cleaned_url = (agent_url or "").strip()
    if not cleaned_url:
        _log.error("open_browser_window: HOST_BROWSER_AGENT_URL chua duoc cau hinh")
        raise AppError(
            ErrorCode.CONFIGURATION,
            (
                "HOST_BROWSER_AGENT_URL chua duoc cau hinh; khong the mo cua so browser "
                "qua agent. Vui long chay host_browser_agent.py tren host va dat "
                "HOST_BROWSER_AGENT_URL (vd: http://127.0.0.1:9999)."
            ),
            503,
        )

    payload: dict[str, Any] = {"service": service.upper(), "email": email}
    if url:
        payload["url"] = url

    open_url = f"{cleaned_url.rstrip('/')}/open"
    _log.info(
        "open_browser_window: forwarding toi %s cho %s/%s",
        open_url,
        service,
        email,
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(open_url, json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as exc:
        _log.error(
            "open_browser_window: timeout ket noi toi host-browser-agent %s: %s",
            open_url,
            exc,
        )
        raise AppError(
            ErrorCode.TIMEOUT,
            f"Timeout ket noi toi host-browser-agent tai {open_url}",
            504,
        ) from exc
    except httpx.HTTPStatusError as exc:
        _log.error(
            "open_browser_window: host-browser-agent tra loi %s: %s",
            exc.response.status_code,
            exc.response.text,
        )
        raise AppError(
            ErrorCode.INTERNAL,
            f"host-browser-agent tra loi {exc.response.status_code}: {exc.response.text}",
            502,
        ) from exc
    except httpx.RequestError as exc:
        _log.error(
            "open_browser_window: khong ket noi duoc toi host-browser-agent %s: %s",
            open_url,
            exc,
        )
        raise AppError(
            ErrorCode.INTERNAL,
            f"Khong ket noi duoc toi host-browser-agent tai {open_url}: {exc}",
            503,
        ) from exc

    launched = data.get("launched")
    pid = data.get("pid")
    if not launched:
        _log.error(
            "open_browser_window: host-browser-agent tu choi launch: %s",
            data,
        )
        raise AppError(
            ErrorCode.INTERNAL,
            f"host-browser-agent tu choi mo browser: {data}",
            502,
        )

    _log.info(
        "open_browser_window: host-browser-agent da mo browser (pid=%s) cho %s/%s",
        pid,
        service,
        email,
    )
    return {"launched": True, "pid": pid}
