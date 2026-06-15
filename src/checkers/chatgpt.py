"""
checkers/chatgpt.py - Check validity and token info for ChatGPT accounts.

Flow:
  1. Auto-refresh access_token if expired (using refresh_token)
  2. GET https://api.openai.com/v1/me -> name, org, role
  3. Display table + persist refreshed tokens when requested
"""
from __future__ import annotations

import asyncio
import base64
import json
from datetime import datetime, timedelta, UTC

import httpx

from ..config.settings import AppConfig, ChatGPTConfig, load_config
from src.core.account_record import (
    AccountRecord,
    Repo,
    build_codex_auth_path,
    serialize_account_record,
    should_export_codex_auth,
    sync_codex_auth_payload,
    write_json,
)
from common.database._async import (
    delete_account_async,
    get_accounts_async,
    update_account_async,
)
from .base import CheckResult

import logging
_log = logging.getLogger(__name__)


def is_expired(expired_iso: str, buffer_sec: int = 300) -> bool:
    """Return True if token expires within buffer_sec seconds, or has no expiry."""
    if not expired_iso:
        return True
    try:
        exp = datetime.fromisoformat(expired_iso)
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=UTC)
        return exp - timedelta(seconds=buffer_sec) <= datetime.now(UTC)
    except Exception as e:  # noqa: BLE001 - HTTP boundary - log and return None
        _log.warning("is_expired parse error: %s", e)
        return True





_WEEK_SECONDS = 604800  # kept for backward compat — use cfg.weekly_quota_window_sec


def _pick_weekly_window(rate_limit: dict | None, weekly_secs: int = _WEEK_SECONDS) -> dict | None:
    """Trả về window có limit_window_seconds == weekly_secs (weekly), ưu tiên primary rồi secondary."""
    if not rate_limit:
        return None
    for key in ("primary_window", "primaryWindow", "secondary_window", "secondaryWindow"):
        w = rate_limit.get(key)
        if not w:
            continue
        secs = w.get("limit_window_seconds") or w.get("limitWindowSeconds")
        try:
            if int(secs) == weekly_secs:
                return w
        except (TypeError, ValueError):
            continue
    return None


def _quota_pct(rate_limit: dict | None) -> str:
    """Lấy % đã dùng từ weekly window của một rate_limit object."""
    if not rate_limit:
        return "?"
    window = _pick_weekly_window(rate_limit)
    if window is None:
        limit_reached = rate_limit.get("limit_reached") or rate_limit.get("limitReached")
        allowed = rate_limit.get("allowed")
        if limit_reached or allowed is False:
            return "100%"
        return "?"
    pct_raw = window.get("used_percent") if window.get("used_percent") is not None else window.get("usedPercent")
    if pct_raw is None:
        limit_reached = rate_limit.get("limit_reached") or rate_limit.get("limitReached")
        allowed = rate_limit.get("allowed")
        if limit_reached or allowed is False:
            return "100%"
        return "?"
    try:
        return f"{100 - round(float(pct_raw))}%"
    except (ValueError, TypeError):
        return "?"


# ── Async functions ──────────────────────────────────────────────────────────

def _parse_token_response(token_data: dict, refresh_token_str: str) -> dict:
    """Pure: parse token response → refreshed dict. Shared by sync/async."""
    access_token = token_data["access_token"]
    payload_part = access_token.split(".")[1]
    payload_part += "=" * (-len(payload_part) % 4)
    payload = json.loads(base64.urlsafe_b64decode(payload_part))
    auth = payload.get("https://api.openai.com/auth", {})
    now = datetime.now(UTC)
    return {
        "access_token": access_token,
        "refresh_token": token_data.get("refresh_token", refresh_token_str),
        "id_token": token_data.get("id_token", ""),
        "account_id": auth.get("chatgpt_account_id", ""),
        "expired": (now + timedelta(seconds=token_data.get("expires_in", 0))).isoformat(timespec="seconds"),
        "last_refresh": now.isoformat(timespec="seconds"),
    }


async def refresh_token(
    refresh_token_str: str,
    client_id: str,
    cfg: ChatGPTConfig | None = None,
) -> dict | None:
    """Exchange refresh token for fresh token bundle."""
    token_url = cfg.oauth_token_url if cfg else "https://auth.openai.com/oauth/token"
    timeout = cfg.refresh_token_timeout_sec if cfg else 20
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                token_url,
                data={
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "refresh_token": refresh_token_str,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if resp.status_code != 200:
            return None
        return _parse_token_response(resp.json(), refresh_token_str)
    except Exception as e:  # noqa: BLE001 - HTTP boundary - log and return None
        _log.warning("refresh_token_async failed: %s", e)
        return None


async def fetch_quota(
    access_token: str,
    account_id: str,
    cfg: ChatGPTConfig | None = None,
) -> dict | None:
    """GET /wham/usage → quota payload or None."""
    quota_url = cfg.quota_url if cfg else "https://chatgpt.com/backend-api/wham/usage"
    quota_ua = cfg.quota_ua if cfg else "codex_cli_rs/0.76.0 (Debian 13.0.0; x86_64) WindowsTerminal"
    timeout = cfg.fetch_quota_timeout_sec if cfg else 10
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                quota_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "User-Agent": quota_ua,
                    "Chatgpt-Account-Id": account_id,
                },
            )
        if resp.status_code != 200:
            return None
        return resp.json()
    except Exception as e:  # noqa: BLE001 - HTTP boundary - log and return None
        _log.warning("fetch_quota_async failed: %s", e)
        return None


async def check_account(
    account: dict,
    client_id: str,
    cfg: ChatGPTConfig | None = None,
) -> CheckResult:
    """Check one account record, refresh tokens when needed."""
    me_url = cfg.me_url if cfg else "https://api.openai.com/v1/me"
    codex_ua = cfg.codex_ua if cfg else "codex_cli_rs/0.101.0 (Mac OS 26.0.1; arm64) Apple_Terminal/464"
    check_me_timeout = cfg.check_me_timeout_sec if cfg else 10

    refresh_token_value = account.get("refresh_token", "")
    access_token = account.get("access_token", "")
    expired = account.get("expired", "")

    refreshed: dict | None = None

    if not access_token or is_expired(expired):
        if not refresh_token_value:
            return {"valid": False, "reason": "no refresh_token", "refreshed": None}
        refreshed = await refresh_token(refresh_token_value, client_id, cfg)
        if not refreshed:
            return {"valid": False, "reason": "token refresh failed", "refreshed": None}
        access_token = refreshed["access_token"]

    try:
        async with httpx.AsyncClient(timeout=check_me_timeout) as client:
            response = await client.get(
                me_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "User-Agent": codex_ua,
                    "Originator": "codex_cli_rs",
                    "Version": "0.101.0",
                },
            )
    except httpx.HTTPError as exc:
        return {"valid": False, "reason": str(exc), "refreshed": refreshed}

    if response.status_code == 401:
        return {"valid": False, "reason": "unauthorized (401)", "refreshed": refreshed}
    if response.status_code != 200:
        return {"valid": False, "reason": f"HTTP {response.status_code}", "refreshed": refreshed}

    me = response.json()
    orgs = me.get("orgs", {}).get("data", [])
    org = orgs[0] if orgs else {}
    return {
        "valid": True,
        "name": me.get("name", ""),
        "user_id": me.get("id", ""),
        "org_id": org.get("id", ""),
        "org_title": org.get("title", "Personal"),
        "role": org.get("role", ""),
        "mfa_enabled": me.get("mfa_flag_enabled", False),
        "account_id": refreshed.get("account_id", account.get("account_id", "")) if refreshed else account.get("account_id", ""),
        "expired": refreshed["expired"] if refreshed else expired,
        "reason": "",
        "refreshed": refreshed,
    }


def format_row(account: dict, result: CheckResult) -> str:
    """Format one output row."""
    email = account.get("email", "?")[:34]
    if result["valid"]:
        expires = result.get("expired", "")[:10]
        quota = result.get("_quota")
        if quota:
            w = _quota_pct(quota.get("rate_limit") or quota.get("rateLimit"))
            cr = _quota_pct(quota.get("code_review_rate_limit") or quota.get("codeReviewRateLimit"))
            return f"{email:<35} {expires:<12} W:{w:<6} CR:{cr}"
        role = result.get("role", "")[:8]
        return f"{email:<35} OK   {role:<9} {expires:<12}"
    fails = result.get("fail_count", 0)
    total = result.get("check_count", 1)
    confirmed = result.get("confirmed_bad", False)
    tag = "BAD" if confirmed else f"BAD({fails}/{total})"
    return f"{email:<35} {tag:<10} {result['reason']}"


_CONFIRM_ROUNDS = 5
_BATCH_CONCURRENCY = 10


async def check_account_confirmed(account: dict, client_id: str) -> CheckResult:
    """
    Check account _CONFIRM_ROUNDS lần song song.
    - Nếu tất cả đều fail → confirmed_bad=True.
    - Nếu ít nhất 1 lần OK → valid=True, fail_count=số lần fail.
    """
    results = await asyncio.gather(
        *[check_account(account, client_id) for _ in range(_CONFIRM_ROUNDS)]
    )
    ok_list = [r for r in results if r["valid"]]
    fail_list = [r for r in results if not r["valid"]]
    if ok_list:
        return {**ok_list[0], "fail_count": len(fail_list), "check_count": _CONFIRM_ROUNDS, "confirmed_bad": False}
    return {**fail_list[-1], "fail_count": _CONFIRM_ROUNDS, "check_count": _CONFIRM_ROUNDS, "confirmed_bad": True}


def _merge_refreshed_tokens(account: dict, refreshed: dict) -> dict:
    """Return a NEW account dict with refreshed token fields merged in. Pure — does not mutate."""
    return {
        **account,
        "access_token": refreshed["access_token"],
        "refresh_token": refreshed["refresh_token"],
        "id_token": refreshed.get("id_token", account.get("id_token", "")),
        "account_id": refreshed.get("account_id", account.get("account_id", "")),
        "expired": refreshed["expired"],
        "last_refresh": refreshed["last_refresh"],
    }


def _build_auth_record(account: dict) -> AccountRecord:
    return AccountRecord(
        service="CHATGPT",
        email=account.get("email", ""),
        password=account.get("password", ""),
        disabled=bool(account.get("disabled", False)),
        refresh_token=account.get("refresh_token", ""),
        access_token=account.get("access_token", ""),
        account_id=account.get("account_id", ""),
        id_token=account.get("id_token", ""),
        expired=account.get("expired", ""),
        last_refresh=account.get("last_refresh", ""),
        token_type=account.get("type", ""),
        created_at=account.get("created_at", ""),
        updated_at=account.get("updated_at", ""),
    )


async def _persist_refreshed(cfg: AppConfig, repo: Repo, accounts: list[dict], results: list[CheckResult]) -> None:
    """Write refreshed tokens back to DB and exported auth files."""
    refreshed_pairs = [
        (acc, result["refreshed"])
        for acc, result in zip(accounts, results)
        if result.get("refreshed")
    ]
    if not refreshed_pairs:
        return

    for acc, refreshed_data in refreshed_pairs:
        merged = _merge_refreshed_tokens(acc, refreshed_data)
        await update_account_async(
            service="chatgpt",
            email=acc["email"],
            fields={
                "access_token": merged["access_token"],
                "refresh_token": merged["refresh_token"],
                "id_token": merged.get("id_token", ""),
                "account_id": merged.get("account_id", ""),
                "expired": merged["expired"],
                "last_refresh": merged["last_refresh"],
            },
        )
        record = _build_auth_record(merged)
        if not should_export_codex_auth(record):
            continue
        payload = serialize_account_record(record, include_timestamps=False)
        write_json(build_codex_auth_path(cfg.base_dir, record.email), payload)
        sync_codex_auth_payload(record.email, payload, cfg.auth_sync)

    print("\nRefreshed tokens saved.")


async def _delete_bad_accounts(
    cfg: AppConfig,
    repo: Repo,
    accounts: list[dict],
    results: list[CheckResult],
) -> None:
    """Xóa bad accounts khỏi DB, auth/, sync dir và cliproxy accounts.json."""
    bad_pairs = [
        (acc, res)
        for acc, res in zip(accounts, results)
        if res and not res["valid"] and res.get("confirmed_bad")
    ]
    if not bad_pairs:
        print("Không có bad account nào.")
        return

    print(f"\n{len(bad_pairs)} bad account(s) sẽ bị xóa:")
    for acc, res in bad_pairs:
        print(f"  {acc.get('email', '?')}  ({res['reason']})")

    confirm = input("\nXác nhận xóa? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Huỷ.")
        return

    bad_emails = {acc.get("email", "") for acc, _ in bad_pairs}

    # 1. Xóa khỏi DB
    deleted_db = 0
    db_errors: list[str] = []
    for email in bad_emails:
        try:
            await delete_account_async(service="chatgpt", email=email)
            deleted_db += 1
        except (OSError, RuntimeError, ValueError) as exc:
            _log.error("delete_account_async(%s) failed: %s", email, exc)
            db_errors.append(email)
    if db_errors:
        _log.warning("%d account(s) failed to delete from DB: %s", len(db_errors), db_errors)

    deleted_local = 0
    deleted_sync = 0

    for email in bad_emails:
        # 2. Xóa auth file trong auth/
        local_path = build_codex_auth_path(cfg.base_dir, email)
        if local_path.exists():
            local_path.unlink()
            deleted_local += 1

        # 3. Xóa auth file trong sync target dir
        if cfg.auth_sync and cfg.auth_sync.enabled:
            sync_path = cfg.auth_sync.target_dir / local_path.name
            if sync_path.exists():
                sync_path.unlink()
                deleted_sync += 1

    # 4. Xóa khỏi cliproxy accounts.json
    deleted_cliproxy = 0
    cliproxy_path = (cfg.auth_sync.target_dir.parent / "accounts.json") if cfg.auth_sync and cfg.auth_sync.enabled else None
    if cliproxy_path and cliproxy_path.exists():
        import json as _json
        raw = _json.loads(cliproxy_path.read_text(encoding="utf-8"))
        codex_accounts = raw.get("providers", {}).get("codex", {}).get("accounts", {})
        for email in bad_emails:
            if email in codex_accounts:
                del codex_accounts[email]
                deleted_cliproxy += 1
        # Cập nhật default nếu nó bị xóa
        default_email = raw.get("providers", {}).get("codex", {}).get("default", "")
        if default_email in bad_emails:
            remaining = list(codex_accounts.keys())
            raw["providers"]["codex"]["default"] = remaining[0] if remaining else ""
        cliproxy_path.write_text(_json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nĐã xóa {deleted_db} account(s) khỏi DB")
    print(f"Đã xóa {deleted_local} auth file(s) trong auth/")
    print(f"Đã xóa {deleted_sync} auth file(s) trong {cfg.auth_sync.target_dir if cfg.auth_sync else 'N/A'}")
    if cliproxy_path:
        print(f"Đã xóa {deleted_cliproxy} account(s) khỏi {cliproxy_path}")


async def _main_async(save_refreshed: bool = True, with_quota: bool = False) -> None:
    cfg = load_config()
    repo = Repo(base_dir=cfg.base_dir, auth_sync=cfg.auth_sync, cliproxy_sync=cfg.cliproxy_sync)
    accounts = await get_accounts_async(service="chatgpt")

    if not accounts:
        print("No ChatGPT accounts found in DB")
        return

    total = len(accounts)
    if with_quota:
        header = f"{'Email':<35} {'Expires':<12} {'W rem':<8} CR rem"
    else:
        header = f"{'Email':<35} {'OK':<4} {'Role':<9} {'Expires':<12} Reason"
    sep = "-" * len(header)
    print(f"\nChecking {total} ChatGPT account(s)...\n")
    print(f"{header}\n{sep}")

    results: list[CheckResult | None] = [None] * total
    sem = asyncio.Semaphore(_BATCH_CONCURRENCY)

    async def _check_one(idx: int, account: dict) -> None:
        async with sem:
            result = await check_account_confirmed(account, cfg.chatgpt.client_id)
            if with_quota and result["valid"]:
                at = result["refreshed"]["access_token"] if result.get("refreshed") else account.get("access_token", "")
                aid = result.get("account_id") or account.get("account_id", "")
                quota_data = await fetch_quota(at, aid)
                if quota_data:
                    result = {**result, "_quota": quota_data}
        results[idx] = result
        done = sum(1 for r in results if r is not None)
        print(f"[{done}/{total}] {format_row(account, result)}", flush=True)

    await asyncio.gather(*[_check_one(i, acc) for i, acc in enumerate(accounts)])

    if save_refreshed:
        await _persist_refreshed(cfg, repo, accounts, results)  # type: ignore[arg-type]

    valid = sum(1 for r in results if r and r["valid"])
    print(f"\n{sep}")
    print(f"Total: {total}  valid: {valid}  invalid: {total - valid}")

    if total - valid > 0:
        confirmed = sum(1 for r in results if r and not r["valid"] and r.get("confirmed_bad"))
        flaky = sum(1 for r in results if r and not r["valid"] and not r.get("confirmed_bad"))
        if flaky:
            print(f"  ({flaky} account(s) fail không nhất quán — bỏ qua, không xóa)")
        if confirmed:
            await _delete_bad_accounts(cfg, repo, accounts, results)  # type: ignore[arg-type]


def main(save_refreshed: bool = True, with_quota: bool = False) -> None:
    asyncio.run(_main_async(save_refreshed, with_quota))


if __name__ == "__main__":
    main()
