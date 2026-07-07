"""services/elevenlabs_io/registrar.py — ElevenLabs registration entrypoint.

Delegate browser work cho Browser Gateway (host camoufox) — container không có
camoufox binary. Gateway task `register_elevenlabs` inject Google storage_state
vào context + chạy `_signup_flow` (xem `flow.py`), trả record dict; container
save_fn lưu DB.

Automation recipe tách riêng trong `flow.py` — file này chỉ orchestration.
"""
from __future__ import annotations

import asyncio
import logging

from ...config.settings import AppConfig
from common.browser_gateway_client import BrowserGatewayError, run_browser_task
from common.database._async import get_mailbox_record_async
from common.database._engine import get_async_session
from src.core.account_record import AccountRecord
from ...mail._base import MailCfg
from ...mail.client import create_mailbox
from ..errors import FatalRegistrationError, NoMailboxAvailableError, NoSessionError, RetryableRegistrationError
from ..protocols import LogFn, SaveFn

_LOG = logging.getLogger(__name__)


async def register_elevenlabs(
    cfg: AppConfig,
    log_fn: LogFn,
    save_fn: SaveFn,
) -> AccountRecord | None:
    """ElevenLabs registration entrypoint (delegate → Browser Gateway)."""
    max_attempts = cfg.register.max_attempts
    for attempt in range(1, max_attempts + 1):
        try:
            providers = cfg.mail.providers_for("elevenlabs")
            mail_cfg = MailCfg(
                cooldown_sec=cfg.mail.cooldown_sec,
                max_consecutive_fails=cfg.mail.max_consecutive_fails,
                testmail_monthly_quota=cfg.mail.testmail_monthly_quota,
            )
            mailbox = await create_mailbox(providers, cfg=mail_cfg, log_fn=log_fn, service_tag="elevenlabs")
        except RuntimeError as e:
            raise NoMailboxAvailableError(str(e)) from e

        if attempt > 1:
            log_fn(f"\n🔄 Retry attempt {attempt}/{max_attempts}")
        log_fn(f"📧 Email: {mailbox.email}")
        log_fn("-" * 50)

        use_session = cfg.elevenlabs.use_google_session

        if use_session:
            # Lấy Google storage_state từ PostgreSQL — bắt buộc phải có
            async with get_async_session() as session:
                mailbox_record = await get_mailbox_record_async(session, mailbox.email)
            state_json = (mailbox_record or {}).get("google_auth_state", "")
            if not state_json:
                raise NoSessionError(
                    f"No Google session found for {mailbox.email} — "
                    "chạy 'Login Google Session' trước để lưu session vào DB"
                )
            log_fn(f"  ✓ Google session loaded ({len(state_json)} bytes)")
        else:
            state_json = None
            log_fn("  ℹ use_google_session=false → login fresh trong popup")

        try:
            gateway_url = cfg.api.host_browser_agent_url
            if not gateway_url:
                raise RuntimeError(
                    "HOST_BROWSER_AGENT_URL chưa cấu hình — không thể register ElevenLabs. "
                    "Chạy Browser Gateway trên host (py registrar/tools/host_browser_agent.py)."
                )
            result = await run_browser_task(
                gateway_url,
                "register_elevenlabs",
                args={"email": mailbox.email, "use_session": use_session},
                on_log=log_fn,
            )
            record = AccountRecord(
                service="ELEVENLABS",
                email=result["email"],
                password=result["password"],
                api_key=result.get("api_key", ""),
            )
            await asyncio.to_thread(save_fn, record)
            log_fn("💾 Saved to DB")
            return record
        except FatalRegistrationError:
            raise
        except BrowserGatewayError as e:
            raise RetryableRegistrationError(str(e)) from e
        except (RuntimeError, RetryableRegistrationError):
            raise
        except Exception:
            _LOG.exception("Unexpected error in elevenlabs registrar")
            raise

    log_fn(f"\n❌ Failed after {max_attempts} attempts")
    return None
