"""
src/captcha/capsolver.py — Captcha solver client hỗ trợ nhiều provider.

Thứ tự ưu tiên (tự động pick theo key nào được set):
  1. YesCaptcha  — FREE 1500 điểm khi đăng ký
  2. EZCaptcha   — rẻ nhất khi mua: Turnstile $1/1k
  3. 2captcha    — min nạp chỉ $3: Turnstile $1.45/1k
  4. CapSolver   — fallback: Turnstile $1.6/1k

API của cả 4 giống nhau (createTask / getTaskResult / clientKey),
chỉ khác base URL và task type name.
"""
from __future__ import annotations

import asyncio
import time
from concurrent.futures import Future
from threading import Thread
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from ..config.settings import CaptchaConfig


def _run_sync(coro):
    """Chạy coroutine từ sync context. An toàn cả khi có/không event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Đã có loop → chạy trong thread mới để tránh deadlock
    result: Future = Future()

    def _runner():
        try:
            result.set_result(asyncio.run(coro))
        except Exception as exc:  # noqa: BLE001 - best-effort captcha UI action
            result.set_exception(exc)

    t = Thread(target=_runner, daemon=True)
    t.start()
    t.join()
    return result.result()

_POLL_INTERVAL = 3   # giây
_MAX_WAIT = 120      # giây

# ── Provider configs ────────────────────────────────────────────────────────

_DEFAULT_PROVIDERS = {
    "yescaptcha": {
        "base": "https://api.yescaptcha.com",
        "turnstile_task": "TurnstileTaskProxyless",
    },
    "ezcaptcha": {
        "base": "https://api.ez-captcha.com",
        "turnstile_task": "CloudFlareTurnstileTask",
    },
    "2captcha": {
        "base": "https://api.2captcha.com",
        "turnstile_task": "TurnstileTaskProxyless",
    },
    "capsolver": {
        "base": "https://api.capsolver.com",
        "turnstile_task": "AntiTurnstileTaskProxyless",
    },
}


def _build_providers(captcha_cfg: CaptchaConfig) -> dict:
    """Build providers dict từ CaptchaConfig, merge với _DEFAULT_PROVIDERS."""
    import copy
    providers = copy.deepcopy(_DEFAULT_PROVIDERS)
    if getattr(captcha_cfg, "yescaptcha_base_url", None):
        providers["yescaptcha"]["base"] = captcha_cfg.yescaptcha_base_url
    elif getattr(captcha_cfg, "yescaptcha_base", None):
        providers["yescaptcha"]["base"] = captcha_cfg.yescaptcha_base
    if getattr(captcha_cfg, "ezcaptcha_base_url", None):
        providers["ezcaptcha"]["base"] = captcha_cfg.ezcaptcha_base_url
    elif getattr(captcha_cfg, "ezcaptcha_base", None):
        providers["ezcaptcha"]["base"] = captcha_cfg.ezcaptcha_base
    return providers


def _detect_provider(ezcaptcha_key: str, capsolver_key: str, twocaptcha_key: str = "") -> tuple[str, str]:
    """Trả về (provider_name, api_key). Ưu tiên: EZCaptcha (rẻ) → 2captcha (min $3) → CapSolver."""
    if ezcaptcha_key:
        return "ezcaptcha", ezcaptcha_key
    if twocaptcha_key:
        return "2captcha", twocaptcha_key
    if capsolver_key:
        return "capsolver", capsolver_key
    raise RuntimeError("Chưa set captcha API key. Cần ít nhất 1 trong: ezcaptcha_api_key / twocaptcha_api_key / capsolver_api_key")


# ── Public API ───────────────────────────────────────────────────────────────

def solve_turnstile(
    api_key: str,
    page_url: str,
    site_key: str,
    timeout: int = _MAX_WAIT,
    provider: str = "ezcaptcha",
) -> str:
    """Sync wrapper — forwards to async impl for backwards compat."""
    return _run_sync(_solve_turnstile_async(api_key, page_url, site_key, timeout, provider))


async def solve_turnstile_async(
    api_key: str,
    page_url: str,
    site_key: str,
    timeout: int = _MAX_WAIT,
    provider: str = "ezcaptcha",
) -> str:
    """
    Gửi task Turnstile tới captcha service, chờ nhận token.
    Returns token string. Raises RuntimeError nếu thất bại hoặc timeout.
    """
    return await _solve_turnstile_async(api_key, page_url, site_key, timeout, provider)


async def _solve_turnstile_async(
    api_key: str,
    page_url: str,
    site_key: str,
    timeout: int,
    provider: str,
    poll_interval_sec: int = _POLL_INTERVAL,
    create_task_timeout_sec: int = 30,
    poll_result_timeout_sec: int = 10,
    providers: dict | None = None,
) -> str:
    cfg = (providers or _DEFAULT_PROVIDERS)[provider]
    task_id = await _create_task(api_key, page_url, site_key, cfg, timeout_sec=create_task_timeout_sec)
    return await _poll_result(api_key, task_id, timeout, cfg, poll_interval_sec=poll_interval_sec, result_timeout_sec=poll_result_timeout_sec)


def solve_turnstile_auto(
    ezcaptcha_key: str,
    capsolver_key: str,
    page_url: str,
    site_key: str,
    timeout: int = _MAX_WAIT,
    yescaptcha_key: str = "",
    twocaptcha_key: str = "",
    use_patchright: bool = False,
    patchright_headless: bool = True,
    turnstile_solver_url: str = "",
) -> str:
    """Sync wrapper — auto-select provider."""
    return _run_sync(solve_turnstile_auto_async(
        ezcaptcha_key, capsolver_key, page_url, site_key, timeout,
        yescaptcha_key, twocaptcha_key, use_patchright, patchright_headless,
        turnstile_solver_url,
    ))


async def _solve_via_turnstile_solver(
    url: str, page_url: str, site_key: str, timeout: int,
    poll_interval_sec: int = _POLL_INTERVAL,
    request_timeout_sec: int = 15,
) -> str:
    """
    Gọi Turnstile-Solver local server (github.com/Theyka/Turnstile-Solver).
    API: GET /turnstile?url=&sitekey= → {task_id}
         GET /result?id=             → "CAPTCHA_NOT_READY" | {value, elapsed_time}
    """
    import urllib.parse
    base = url.rstrip("/")
    params = urllib.parse.urlencode({"url": page_url, "sitekey": site_key})
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{base}/turnstile?{params}", timeout=request_timeout_sec)
        resp.raise_for_status()
        task_id = resp.json()["task_id"]

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{base}/result?id={task_id}", timeout=request_timeout_sec)
            r.raise_for_status()
        # Response có thể là plain string "CAPTCHA_NOT_READY" hoặc JSON object
        text = r.text.strip().strip('"')
        if text == "CAPTCHA_NOT_READY":
            await asyncio.sleep(poll_interval_sec)
            continue
        try:
            data = r.json()
        except Exception:  # noqa: BLE001 - best-effort captcha UI action
            data = {}
        value = data.get("value", text) if isinstance(data, dict) else text
        if value == "CAPTCHA_FAIL":
            raise RuntimeError(f"Turnstile-Solver: CAPTCHA_FAIL (task={task_id})")
        if value:
            return value
        await asyncio.sleep(poll_interval_sec)

    raise RuntimeError(f"Turnstile-Solver: timeout sau {timeout}s (task={task_id})")


async def solve_turnstile_auto_async(
    ezcaptcha_key: str,
    capsolver_key: str,
    page_url: str,
    site_key: str,
    timeout: int = _MAX_WAIT,
    yescaptcha_key: str = "",
    twocaptcha_key: str = "",
    use_patchright: bool = False,
    patchright_headless: bool = True,
    turnstile_solver_url: str = "",
    captcha_cfg: CaptchaConfig | None = None,
) -> str:
    """Auto-select provider:
    1. Turnstile-Solver local server (camoufox, không key) — ưu tiên nhất
    2. patchright local
    3. YesCaptcha → EZCaptcha → 2captcha → CapSolver (API key)
    """
    poll_interval = captcha_cfg.poll_interval_sec if captcha_cfg else _POLL_INTERVAL
    create_timeout = captcha_cfg.create_task_timeout_sec if captcha_cfg else 30
    poll_timeout = captcha_cfg.poll_result_timeout_sec if captcha_cfg else 10
    ts_timeout = captcha_cfg.turnstile_solver_timeout_sec if captcha_cfg else 15
    providers = _build_providers(captcha_cfg) if captcha_cfg else _DEFAULT_PROVIDERS

    if turnstile_solver_url:
        return await _solve_via_turnstile_solver(
            turnstile_solver_url, page_url, site_key, timeout,
            poll_interval_sec=poll_interval, request_timeout_sec=ts_timeout,
        )
    if use_patchright:
        from .patchright_solver import solve_turnstile_patchright_async
        return await solve_turnstile_patchright_async(
            page_url, site_key, timeout=timeout, headless=patchright_headless,
            viewport_width=captcha_cfg.patchright_viewport_width if captcha_cfg else 1280,
            viewport_height=captcha_cfg.patchright_viewport_height if captcha_cfg else 800,
            page_load_timeout_ms=captcha_cfg.patchright_page_load_timeout_ms if captcha_cfg else 40_000,
            poll_interval_sec=captcha_cfg.patchright_poll_interval_sec if captcha_cfg else 0.5,
        )
    if yescaptcha_key:
        return await _solve_turnstile_async(
            yescaptcha_key, page_url, site_key, timeout, "yescaptcha",
            poll_interval, create_timeout, poll_timeout, providers,
        )
    provider, api_key = _detect_provider(ezcaptcha_key, capsolver_key, twocaptcha_key)
    return await _solve_turnstile_async(
        api_key, page_url, site_key, timeout, provider,
        poll_interval, create_timeout, poll_timeout, providers,
    )


async def get_balance_async(
    api_key: str,
    provider: str = "ezcaptcha",
    balance_timeout_sec: int = 15,
    captcha_cfg: CaptchaConfig | None = None,
) -> float:
    """Trả về balance (điểm hoặc USD) còn lại."""
    providers = _build_providers(captcha_cfg) if captcha_cfg else _DEFAULT_PROVIDERS
    timeout = captcha_cfg.balance_timeout_sec if captcha_cfg else balance_timeout_sec
    base = providers[provider]["base"]
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{base}/getBalance", json={"clientKey": api_key}, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    if data.get("errorId", 0) != 0:
        raise RuntimeError(f"{provider} getBalance error: {data.get('errorDescription')}")
    return float(data.get("balance", 0))


def get_balance(
    api_key: str,
    provider: str = "ezcaptcha",
    balance_timeout_sec: int = 15,
    captcha_cfg: CaptchaConfig | None = None,
) -> float:
    """Sync wrapper for get_balance_async."""
    return _run_sync(get_balance_async(api_key, provider, balance_timeout_sec, captcha_cfg))


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _create_task(
    api_key: str, page_url: str, site_key: str, cfg: dict,
    timeout_sec: int = 30,
) -> str:
    payload = {
        "clientKey": api_key,
        "task": {
            "type": cfg["turnstile_task"],
            "websiteURL": page_url,
            "websiteKey": site_key,
        },
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{cfg['base']}/createTask", json=payload, timeout=timeout_sec)
    resp.raise_for_status()
    data = resp.json()

    if data.get("errorId", 0) != 0:
        raise RuntimeError(f"createTask error: {data.get('errorCode')} — {data.get('errorDescription')}")

    task_id = data.get("taskId")
    if not task_id:
        raise RuntimeError(f"no taskId in response: {data}")
    return task_id


async def _poll_result(
    api_key: str, task_id: str, timeout: int, cfg: dict,
    poll_interval_sec: int = _POLL_INTERVAL,
    result_timeout_sec: int = 10,
) -> str:
    payload = {"clientKey": api_key, "taskId": task_id}
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{cfg['base']}/getTaskResult", json=payload, timeout=result_timeout_sec)
        resp.raise_for_status()
        data = resp.json()

        if data.get("errorId", 0) != 0:
            raise RuntimeError(f"getTaskResult error: {data.get('errorCode')} — {data.get('errorDescription')}")

        status = data.get("status")
        if status == "ready":
            token = data.get("solution", {}).get("token")
            if not token:
                raise RuntimeError(f"status=ready but no token: {data}")
            return token

        if status == "failed":
            raise RuntimeError(f"task failed: {data}")

        await asyncio.sleep(poll_interval_sec)

    raise RuntimeError(f"timeout after {timeout}s waiting for task {task_id}")
