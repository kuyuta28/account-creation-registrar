"""
checker_service.py — Business logic cho account checking.
Responsibilities:
  - check_and_persist: gọi checker tương ứng, persist kết quả vào DB
  - Batch check: orchestrate async check nhiều accounts
  - OR Privacy check: kiểm tra model access restriction
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from ...checkers.base import AccountCheckerProtocol
from ...config.settings import load_config
from common.database._async import (
    delete_account_async,
    get_account_by_email_async,
    get_accounts_async,
    update_account_async,
)
from common.database._engine import get_async_session
from common.enums import CheckStatus

_log = logging.getLogger(__name__)


# ── Batch check state ──────────────────────────────────────────────
_batch_lock = asyncio.Lock()
_batch: dict[str, Any] = {
    "running": False,
    "total": 0,
    "checked": 0,
    "valid": 0,
    "invalid": 0,
    "errors": 0,
    "results": [],
}

# ── OR Privacy check state ─────────────────────────────────────────────
_or_privacy_lock = asyncio.Lock()
_or_privacy_batch: dict[str, Any] = {
    "running": False,
    "total": 0,
    "checked": 0,
    "ok": 0,
    "privacy_blocked": 0,
    "skipped": 0,
}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


# ── Checker implementations (Strategy) ────────────────────────────────

async def _check_chatgpt(account: dict[str, Any], cfg: Any, now: str) -> dict[str, Any]:
    from ...checkers.chatgpt import check_account, fetch_quota, _quota_pct

    result = await check_account(account, cfg.chatgpt.client_id, cfg.chatgpt)
    check_status = CheckStatus.VALID if result["valid"] else CheckStatus.INVALID
    last_error = result.get("reason", "") if not result["valid"] else ""
    quota_pct = ""

    if result["valid"]:
        refreshed = result.get("refreshed") or {}
        at = refreshed.get("access_token") or account.get("access_token", "")
        aid = result.get("account_id") or account.get("account_id", "")
        quota_data = await fetch_quota(at, aid, cfg.chatgpt)
        if quota_data:
            rl = quota_data.get("rate_limit") or quota_data.get("rateLimit")
            quota_pct = _quota_pct(rl)

    update_fields: dict[str, Any] = {
        "check_status": check_status,
        "quota_pct": quota_pct,
        "last_checked": now,
        "last_error": last_error,
    }
    if result.get("refreshed"):
        r = result["refreshed"]
        update_fields.update({
            "access_token": r.get("access_token", ""),
            "refresh_token": r.get("refresh_token", ""),
            "id_token": r.get("id_token", ""),
            "account_id": r.get("account_id", ""),
            "expired": r.get("expired", ""),
            "last_refresh": r.get("last_refresh", ""),
        })

    async with get_async_session() as session:
        await update_account_async(session, "CHATGPT", account["email"], **update_fields)
    return {
        "valid": result["valid"],
        "check_status": check_status,
        "quota_pct": quota_pct,
        "last_checked": now,
        "last_error": last_error,
        "name": result.get("name", ""),
        "token_refreshed": result.get("refreshed") is not None,
    }


async def _check_elevenlabs(account: dict[str, Any], cfg: Any, now: str) -> dict[str, Any]:
    from ...checkers.elevenlabs import check_key

    api_key = account.get("api_key", "")
    result = await check_key(api_key, cfg.elevenlabs)
    last_error = result.get("reason", "") if not result["valid"] else ""
    is_unusual = "unusual_activity" in last_error
    check_status = CheckStatus.INVALID if not result["valid"] else CheckStatus.VALID
    quota_pct = ""
    if result["valid"]:
        used = result.get("characters_used", 0)
        limit = result.get("characters_limit", 0)
        if limit > 0:
            quota_pct = f"{round((limit - used) / limit * 100)}%"

    update_kwargs: dict[str, Any] = {
        "check_status": check_status,
        "quota_pct": quota_pct,
        "last_checked": now,
        "last_error": last_error,
    }
    if is_unusual:
        update_kwargs["disabled"] = True
        _log.warning("ELEVENLABS %s: unusual_activity — auto-disabled", account["email"])

    async with get_async_session() as session:
        await update_account_async(session, "ELEVENLABS", account["email"], **update_kwargs)
    return {
        "valid": result["valid"],
        "check_status": check_status,
        "quota_pct": quota_pct,
        "last_checked": now,
        "last_error": last_error,
        "token_refreshed": False,
    }


async def _check_openrouter(account: dict[str, Any], cfg: Any, now: str) -> dict[str, Any]:
    from ...checkers.openrouter import check_key_async

    api_key = account.get("api_key", "")
    result = await check_key_async(api_key, cfg.openrouter)
    check_status = CheckStatus.VALID if result["valid"] else CheckStatus.INVALID
    last_error = result.get("reason", "") if not result["valid"] else ""
    quota_pct = ""
    if result["valid"]:
        limit = result.get("limit")
        remaining = result.get("limit_remaining")
        if limit and limit > 0 and remaining is not None:
            quota_pct = f"{round(remaining / limit * 100)}%"

    async with get_async_session() as session:
        await update_account_async(session, "OPENROUTER", account["email"], **{
        "check_status": check_status,
        "quota_pct": quota_pct,
        "last_checked": now,
        "last_error": last_error,
    })
    return {
        "valid": result["valid"],
        "check_status": check_status,
        "quota_pct": quota_pct,
        "last_checked": now,
        "last_error": last_error,
        "token_refreshed": False,
    }


async def _check_aa_session(account: dict[str, Any], cfg: Any, now: str) -> dict[str, Any]:
    """Check session AA còn hạn không bằng cách gọi /api/auth/get-session."""
    import httpx

    session_state = account.get("session_state", "")
    if not session_state:
        check_status = CheckStatus.EXPIRED
        async with get_async_session() as session:
            await update_account_async(session, "ARTIFICIALANALYSIS", account["email"], **{
            "check_status": check_status,
            "last_checked": now,
            "last_error": "no session_state",
        })
        return {"valid": False, "check_status": check_status, "last_checked": now, "last_error": "no session_state"}

    from ...api.routers.aa_proxy import _build_cookies, _build_headers, _aa_cfg
    cookies = _build_cookies(session_state)
    aa_cfg = _aa_cfg()

    try:
        async with httpx.AsyncClient(timeout=aa_cfg.check_timeout_sec) as client:
            r = await client.get(
                f"{aa_cfg.base_url}/api/auth/get-session",
                cookies=cookies,
                headers=_build_headers(),
            )

        body = r.json() if r.status_code == 200 else None
        if r.status_code == 401 or (r.status_code == 200 and not (body or {}).get("session")):
            check_status = CheckStatus.EXPIRED
            last_error = "session expired"
        elif r.status_code == 200:
            check_status = CheckStatus.VALID
            last_error = ""
        else:
            check_status = CheckStatus.ERROR
            last_error = f"HTTP {r.status_code}"

    except (httpx.HTTPError, ValueError, KeyError) as exc:
        check_status = CheckStatus.ERROR
        last_error = str(exc)[:200]

    async with get_async_session() as session:
        await update_account_async(session, "ARTIFICIALANALYSIS", account["email"], **{
        "check_status": check_status,
        "last_checked": now,
        "last_error": last_error,
    })
    return {
        "valid": check_status == CheckStatus.VALID,
        "check_status": check_status,
        "last_checked": now,
        "last_error": last_error,
        "token_refreshed": False,
    }


# CheckerFn = (account_row, cfg, now_str) -> result_dict
CheckerFn = Callable[[dict[str, Any], Any, str], Awaitable[dict[str, Any]]]

_CHECKERS: dict[str, AccountCheckerProtocol] = {
    "CHATGPT": _check_chatgpt,  # type: ignore[dict-item]
    "ELEVENLABS": _check_elevenlabs,  # type: ignore[dict-item]
    "OPENROUTER": _check_openrouter,  # type: ignore[dict-item]
    "ARTIFICIALANALYSIS": _check_aa_session,  # type: ignore[dict-item]
}


async def check_and_persist(service: str, email: str) -> dict[str, Any]:
    """Check account validity/quota rồi persist kết quả vào DB.
    Dùng Strategy registry — thêm service mới chỉ cần thêm vào _CHECKERS.
    """
    async with get_async_session() as session:
        account = await get_account_by_email_async(session, service.upper(), email)
    if not account:
        return {"error": "not found"}

    cfg = load_config()
    now = _now()

    checker = _CHECKERS.get(service.upper())
    if checker is None:
        raise ValueError(f"No checker available for service: {service}")
    return await checker(account, cfg, now)


async def get_openrouter_key_detail(api_key: str) -> dict[str, Any]:
    """Fetch full OpenRouter key detail for UI modal."""
    cfg = load_config()
    from ...checkers.openrouter import get_key_detail
    return await get_key_detail(api_key, cfg.openrouter)


# ── Batch check ────────────────────────────────────────────────────────

async def get_batch_status() -> dict[str, Any]:
    async with _batch_lock:
        return dict(_batch)


async def start_batch_check(service: str | None = None) -> dict[str, Any]:
    """Start background batch check. service=None defaults to CHATGPT."""
    target = (service or "CHATGPT").upper()

    if target not in _CHECKERS:
        return {"error": f"No checker available for service: {target}"}

    async with _batch_lock:
        if _batch["running"]:
            return {"error": "already running", **_batch}

    async with get_async_session() as session:
        accounts = await get_accounts_async(session, target, False)
    total = len(accounts)
    if total == 0:
        return {"error": "no accounts to check"}

    async with _batch_lock:
        _batch["running"] = True
        _batch["total"] = total
        _batch["checked"] = 0
        _batch["valid"] = 0
        _batch["invalid"] = 0
        _batch["errors"] = 0
        _batch["results"] = []

    cfg = load_config()
    _sem = asyncio.Semaphore(cfg.checker.batch_concurrency)

    async def _check_one(acc: dict[str, Any]) -> None:
        email = acc["email"]
        async with _sem:
            try:
                result = await check_and_persist(target, email)
                cs = result.get("check_status", "error")
                err = result.get("last_error", "")
                qp = result.get("quota_pct", "")
                is_err = "error" in result and "check_status" not in result
                async with _batch_lock:
                    _batch["checked"] += 1
                    if is_err:
                        _batch["errors"] += 1
                    elif cs == "valid":
                        _batch["valid"] += 1
                    else:
                        _batch["invalid"] += 1
                    _batch["results"].append(
                        {"email": email, "check_status": cs, "quota_pct": qp, "error": err}
                    )
            except Exception as exc:  # noqa: BLE001 - batch collector: per-item isolation
                _log.warning("Batch check failed for %s: %s", email, exc)
                async with _batch_lock:
                    _batch["checked"] += 1
                    _batch["errors"] += 1
                    _batch["results"].append(
                        {"email": email, "check_status": "error", "quota_pct": "", "error": str(exc)}
                    )

    async def _worker():
        await asyncio.gather(*[_check_one(acc) for acc in accounts])
        async with _batch_lock:
            _batch["running"] = False
        _log.info("Batch check done: %d/%d", _batch["checked"], _batch["total"])

    asyncio.create_task(_worker())
    return {"ok": True, "total": total}


# ── OpenRouter privacy check ───────────────────────────────────────────

async def _check_or_privacy_one(api_key: str, cfg: Any) -> str:
    """Returns: 'ok' | 'privacy_blocked' | 'skipped'"""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=cfg.check_timeout_sec) as client:
            resp = await client.post(
                cfg.chat_completions_url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": cfg.privacy_check_model,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 1,
                },
            )
        if resp.status_code == 200:
            return "ok"
        if resp.status_code == 404:
            msg = resp.json().get("error", {}).get("message", "")
            if "guardrail" in msg.lower() or "privacy" in msg.lower() or "data policy" in msg.lower():
                return "privacy_blocked"
        return "skipped"
    except Exception as exc:  # noqa: BLE001 - batch collector: per-item isolation
        _log.warning("OR privacy check network error for key ...%s: %s", api_key[-6:], exc)
        return "skipped"


async def _run_or_privacy_check(accounts: list[dict[str, Any]]) -> None:
    now = _now()
    cfg = load_config().openrouter

    async def _process(acc: dict[str, Any]) -> None:
        result = await _check_or_privacy_one(acc["api_key"], cfg)
        if result == "privacy_blocked":
            async with get_async_session() as session:
                await update_account_async(session, "OPENROUTER", acc["email"],
                check_status="invalid", last_checked=now, last_error="privacy settings blocked",)
        elif result == "ok":
            async with get_async_session() as session:
                await update_account_async(session, "OPENROUTER", acc["email"],
                check_status="valid", last_checked=now, last_error="",)
        if result not in ("ok", "privacy_blocked", "skipped"):
            raise ValueError(f"Unexpected privacy check result: {result!r}")
        async with _or_privacy_lock:
            _or_privacy_batch["checked"] += 1
            _or_privacy_batch[result] += 1

    await asyncio.gather(*[_process(acc) for acc in accounts])

    async with _or_privacy_lock:
        _or_privacy_batch["running"] = False


async def start_or_privacy_check() -> dict[str, Any]:
    async with _or_privacy_lock:
        if _or_privacy_batch["running"]:
            return {"error": "already running"}
        async with get_async_session() as session:
            accounts = await get_accounts_async(session, "OPENROUTER", include_disabled=False)
        keys = [a for a in accounts if a.get("api_key")]
        if not keys:
            return {"error": "no openrouter accounts with api_key"}
        _or_privacy_batch.update({
            "running": True,
            "total": len(keys),
            "checked": 0,
            "ok": 0,
            "privacy_blocked": 0,
            "skipped": 0,
        })

    asyncio.create_task(_run_or_privacy_check(keys))
    return {"total": len(keys)}


async def get_or_privacy_status() -> dict[str, Any]:
    async with _or_privacy_lock:
        return dict(_or_privacy_batch)


# ── Check-and-clean OpenRouter (test real API call, xóa dead keys) ─────────────

_clean_or_lock = asyncio.Lock()
_clean_or_batch: dict[str, Any] = {
    "running": False, "total": 0, "checked": 0,
    "ok": 0, "deleted_db": 0, "deleted_cliproxy": 0,
}


async def _test_or_key(api_key: str, semaphore: asyncio.Semaphore) -> bool:
    import httpx
    cfg = load_config()
    async with semaphore:
        try:
            async with httpx.AsyncClient(timeout=cfg.openrouter.check_clean_timeout_sec) as c:
                r = await c.post(
                    cfg.openrouter.chat_completions_url,
                    json={"model": cfg.openrouter.check_clean_model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": cfg.openrouter.check_clean_max_tokens},
                    headers={"Authorization": f"Bearer {api_key}"},
                )
            return r.status_code == 200
        except Exception:  # noqa: BLE001 - batch collector: per-item isolation
            return False


async def _run_check_and_clean_or(accounts: list[dict[str, Any]]) -> None:
    import yaml

    cfg = load_config()
    sem = asyncio.Semaphore(cfg.checker.check_and_clean_concurrency)

    results: list[dict] = []

    async def _check_one(acc: dict) -> None:
        api_key = acc.get("api_key", "")
        ok_result = await _test_or_key(api_key, sem) if api_key else False
        results.append({"email": acc["email"], "api_key": api_key, "ok": ok_result})
        async with _clean_or_lock:
            _clean_or_batch["checked"] += 1
            if ok_result:
                _clean_or_batch["ok"] += 1

    await asyncio.gather(*(_check_one(a) for a in accounts))

    # Xóa DB
    dead = [r for r in results if not r["ok"]]
    async with get_async_session() as session:
        for r in dead:
            await delete_account_async(session, "OPENROUTER", r["email"])
    async with _clean_or_lock:
        _clean_or_batch["deleted_db"] = len(dead)

    # Xóa CLIProxy
    valid_keys = {r["api_key"] for r in results if r["ok"] and r["api_key"]}
    cliproxy_path = Path(cfg.cliproxy_sync.config_path)
    deleted_cp = 0
    if cliproxy_path.exists():
        raw = await asyncio.to_thread(lambda: yaml.safe_load(cliproxy_path.read_text(encoding="utf-8")))
        compat = raw.get("openai-compatibility") or []
        or_entry = next((e for e in compat if str(e.get("name", "")).lower() == "openrouter"), None)
        if or_entry:
            before = or_entry.get("api-key-entries") or []
            after = [e for e in before if isinstance(e, dict) and e.get("api-key") in valid_keys]
            deleted_cp = len(before) - len(after)
            if deleted_cp:
                or_entry["api-key-entries"] = after
                await asyncio.to_thread(
                    lambda: cliproxy_path.write_text(
                        yaml.dump(raw, allow_unicode=True, default_flow_style=False, sort_keys=False),
                        encoding="utf-8",
                    )
                )
    async with _clean_or_lock:
        _clean_or_batch["deleted_cliproxy"] = deleted_cp
        _clean_or_batch["running"] = False


async def start_check_and_clean_or() -> dict[str, Any]:
    async with _clean_or_lock:
        if _clean_or_batch["running"]:
            return {"error": "already running"}
        async with get_async_session() as session:
            accounts = await get_accounts_async(session, "OPENROUTER", include_disabled=False)
        accs = [a for a in accounts if a.get("api_key")]
        if not accs:
            return {"error": "no openrouter accounts with api_key"}
        _clean_or_batch.update({
            "running": True, "total": len(accs), "checked": 0,
            "ok": 0, "deleted_db": 0, "deleted_cliproxy": 0,
        })
    asyncio.create_task(_run_check_and_clean_or(accs))
    return {"total": len(accs)}


async def get_check_and_clean_or_status() -> dict[str, Any]:
    async with _clean_or_lock:
        return dict(_clean_or_batch)


# ── Fix OpenRouter privacy (bật toggles qua Playwright) ────────────────────────

_fix_privacy_lock = asyncio.Lock()
_fix_privacy_batch: dict[str, Any] = {
    "running": False, "total": 0, "processed": 0,
    "ok": 0, "failed": 0, "skipped": 0,
}

_ZDR_KEYWORDS = ("zdr", "zero data retention")


async def _fix_privacy_one(page: Any, email: str, password: str, debug_dir: Path) -> dict:
    from common.page_utils import dump_debug_html as _dump

    cfg = load_config()

    # Login
    await page.goto(cfg.openrouter.sign_in_url, timeout=60_000, wait_until="domcontentloaded")
    await page.wait_for_timeout(3_000)
    await page.locator("input[name=identifier]").fill(email)
    await page.wait_for_timeout(300)
    await page.locator("input[type=password]").fill(password)
    await page.wait_for_timeout(300)

    btns = await page.locator("button").all()
    for b in btns:
        txt = (await b.inner_text()).strip().lower()
        if any(kw in txt for kw in ("google", "apple", "github", "facebook")):
            continue
        if txt in ("continue", "sign in", "submit", "log in"):
            await b.click()
            break
    await page.wait_for_timeout(4_000)

    logged_in = False
    for _ in range(cfg.google_oauth.login_max_iterations):
        url = page.url.lower()
        if "openrouter.ai" in url and "sign-in" not in url and "clerk." not in url:
            logged_in = True
            break
        await page.wait_for_timeout(cfg.openrouter.login_poll_interval_ms)

    if not logged_in:
        await _dump(page, "fix_privacy_login_fail.html", debug_dir)
        return {"status": "login_failed"}

    # Fix toggles
    await page.goto(cfg.openrouter.privacy_settings_url, timeout=60_000, wait_until="domcontentloaded")
    await page.wait_for_timeout(2_000)
    toggles = page.locator('button[role="switch"]')
    count = await toggles.count()
    enabled = 0
    for i in range(count):
        toggle = toggles.nth(i)
        state = await toggle.get_attribute("data-state")
        label = ((await toggle.get_attribute("aria-label")) or f"toggle-{i}").lower()
        if any(kw in label for kw in _ZDR_KEYWORDS):
            continue
        if state != "checked":
            await toggle.click()
            await page.wait_for_timeout(cfg.openrouter.privacy_toggle_wait_ms)
            enabled += 1
    return {"status": "ok", "enabled": enabled}


async def _run_fix_or_privacy(accounts: list[dict[str, Any]]) -> None:
    from common.browser import open_browser

    cfg = load_config()
    sem = asyncio.Semaphore(cfg.checker.fix_privacy_concurrency)

    async def _process(acc: dict) -> None:
        email = acc["email"]
        password = acc.get("password", "")
        if not password:
            async with _fix_privacy_lock:
                _fix_privacy_batch["skipped"] += 1
                _fix_privacy_batch["processed"] += 1
            return
        async with sem:
            try:
                async with open_browser(cfg) as browser:
                    page = await browser.new_page()
                    result = await _fix_privacy_one(page, email, password, cfg.base_dir / "debug")
                async with _fix_privacy_lock:
                    _fix_privacy_batch["processed"] += 1
                    if result["status"] == "ok":
                        _fix_privacy_batch["ok"] += 1
                    else:
                        _fix_privacy_batch["failed"] += 1
            except Exception:  # noqa: BLE001 - batch collector: per-item isolation
                async with _fix_privacy_lock:
                    _fix_privacy_batch["processed"] += 1
                    _fix_privacy_batch["failed"] += 1

    await asyncio.gather(*(_process(a) for a in accounts))
    async with _fix_privacy_lock:
        _fix_privacy_batch["running"] = False


async def start_fix_or_privacy() -> dict[str, Any]:
    async with _fix_privacy_lock:
        if _fix_privacy_batch["running"]:
            return {"error": "already running"}
        async with get_async_session() as session:
            accounts = await get_accounts_async(session, "OPENROUTER", include_disabled=False)
        accs = [a for a in accounts if a.get("password")]
        if not accs:
            return {"error": "no openrouter accounts with password"}
        _fix_privacy_batch.update({
            "running": True, "total": len(accs), "processed": 0,
            "ok": 0, "failed": 0, "skipped": 0,
        })
    asyncio.create_task(_run_fix_or_privacy(accs))
    return {"total": len(accs)}


async def get_fix_or_privacy_status() -> dict[str, Any]:
    async with _fix_privacy_lock:
        return dict(_fix_privacy_batch)


# ── Refresh Kling session (visit site để slide expiry) ───────────────────────

async def refresh_kling_session(email: str) -> dict[str, Any]:
    """Load session_state của account KLING, visit app.klingai.com để refresh cookies, lưu lại."""
    import json
    from common.browser import open_browser

    cfg = load_config()
    async with get_async_session() as session:
        acc = await get_account_by_email_async(session, "KLING", email)
    if not acc:
        return {"error": f"account not found: {email}"}
    session_json = acc.get("session_state", "")
    if not session_json:
        return {"error": "no session_state saved for this account"}

    storage_state = json.loads(session_json)

    KEYS = {"passToken", "userId", "ksi18n.ai.portal_st", "kGateway-identity"}

    def _get_expiries(state: dict) -> dict:
        return {c["name"]: c["expires"] for c in state.get("cookies", []) if c["name"] in KEYS and c.get("expires", 0) > 0}

    before = _get_expiries(storage_state)

    async with open_browser(cfg) as browser:
        ctx = await browser.new_context(storage_state=storage_state)
        page = await ctx.new_page()
        await page.goto(cfg.klingai.refresh_start_url, wait_until="commit", timeout=cfg.klingai.refresh_start_timeout_ms)
        await page.wait_for_timeout(cfg.klingai.refresh_start_wait_ms)
        await page.goto(cfg.klingai.refresh_target_url, wait_until="commit", timeout=cfg.klingai.refresh_target_timeout_ms)
        await page.wait_for_timeout(cfg.klingai.refresh_target_wait_ms)
        new_state = await ctx.storage_state()
        await ctx.close()

    after = _get_expiries(new_state)
    diff = {k: round((after.get(k, 0) - before.get(k, 0)) / 86400, 1) for k in KEYS if k in before and k in after}
    sliding = any(v > 0.1 for v in diff.values())

    if sliding:
        async with get_async_session() as session:
            await update_account_async(session, "KLING", email, {"session_state": json.dumps(new_state)})

    return {"email": email, "sliding": sliding, "diff_days": diff, "saved": sliding}
