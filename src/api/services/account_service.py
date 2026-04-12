"""
account_service.py — CRUD operations on accounts DB.
Single responsibility: create/read/update/delete accounts.
All public functions are async — safe to call from FastAPI async routes.
DB operations use asyncio.to_thread to avoid blocking the event loop.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from ...config.settings import load_config
from common.database import (
    add_service,
    delete_account,
    delete_service,
    get_account_by_email,
    get_accounts,
    get_distinct_services,
    insert_account,
    service_exists,
    update_account,
    upsert_mailbox_record,
)
from src.core.storage import db_path

_log = logging.getLogger(__name__)


def _db_path() -> Path:
    """Lazy: Đọc db_path từ config mỗi lần gọi — không chạy tại import time."""
    return db_path(load_config().base_dir)


async def list_accounts(service: str | None = None) -> list[dict[str, Any]]:
    accounts = await asyncio.to_thread(get_accounts, _db_path(), service)
    return [a for a in accounts if a["service"] != "GMAIL"]


async def list_services() -> list[str]:
    services = await asyncio.to_thread(get_distinct_services, _db_path())
    return [s for s in services if s != "GMAIL"]


async def has_service(service: str) -> bool:
    return await asyncio.to_thread(service_exists, _db_path(), service)


async def get_account(service: str, email: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(get_account_by_email, _db_path(), service, email)


async def update_account_fields(service: str, email: str, **fields) -> bool:
    return await asyncio.to_thread(update_account, _db_path(), service, email, **fields)


async def add_account(
    service: str,
    email: str,
    api_key: str = "",
    password: str = "",
    totp_secret: str = "",
    app_password: str = "",
    source_email: str = "",
) -> bool:
    from src.core.storage import AccountRecord
    from src.core.gmail_variations import _parse_gmail, normalize_gmail

    clean_source_email = source_email.strip()
    if clean_source_email and _parse_gmail(clean_source_email):
        clean_source_email = normalize_gmail(clean_source_email)

    record = AccountRecord(
        service=service.upper(),
        email=email,
        api_key=api_key,
        password=password,
        totp_secret=totp_secret,
        app_password=app_password,
        source_email=clean_source_email,
    )
    inserted = await asyncio.to_thread(insert_account, _db_path(), record)

    # Auto-upsert mailbox khi account có Gmail email hoặc source_email + app_password
    # Mailbox là credential của hòm thư Gmail, không phải của service account
    if app_password and inserted:
        mailbox_email: str | None = None
        if clean_source_email and _parse_gmail(clean_source_email):
            mailbox_email = clean_source_email  # alias account — mailbox là source
        elif _parse_gmail(email):
            mailbox_email = normalize_gmail(email)  # direct Gmail account
        if mailbox_email:
            await asyncio.to_thread(
                upsert_mailbox_record,
                _db_path(), mailbox_email, app_password=app_password, totp_secret=totp_secret, disabled=False,
            )

    return inserted


async def remove_account(service: str, email: str) -> bool:
    return await asyncio.to_thread(delete_account, _db_path(), service, email)


async def remove_disabled_accounts(service: str) -> int:
    from common.database import delete_disabled_service_accounts
    return await asyncio.to_thread(delete_disabled_service_accounts, _db_path(), service.upper())


async def create_service(name: str, has_registrar: bool = False) -> bool:
    return await asyncio.to_thread(add_service, _db_path(), name, has_registrar)


async def destroy_service(name: str) -> bool:
    return await asyncio.to_thread(delete_service, _db_path(), name)

