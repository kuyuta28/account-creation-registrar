"""
account_service.py — CRUD operations on accounts DB using PostgreSQL.
Single responsibility: create/read/update/delete accounts.
All public functions are async — safe to call from FastAPI async routes.
"""
from __future__ import annotations

import os
from typing import Any

# Trigger .env loading (DATABASE_URL) before anything else accesses it
from common import env as _common_env  # noqa: F401

from common.database._async import (
    insert_account_async,
    get_account_by_email_async,
    update_account_async,
    delete_account_async,
    delete_disabled_accounts_async,
    add_service_async,
    delete_service_async,
    list_services_async,
    service_exists_async,
    get_accounts_async,
    upsert_mailbox_async,
    count_accounts_async,
)
from common.database._engine import init_async_db, get_async_session

# Init async DB at module load time
_db_url = os.getenv("DATABASE_URL")
if _db_url:
    init_async_db(_db_url)


async def list_accounts(
    service: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    """List accounts with pagination support.

    Returns:
        dict with:
          - accounts: list of account dicts
          - total: total count
          - limit: page size
          - offset: current offset
    """
    async with get_async_session() as session:
        accounts = await get_accounts_async(session, service, limit=limit, offset=offset, exclude_service="GMAIL")
        total = await count_accounts_async(session, service, exclude_service="GMAIL")
        return {
            "accounts": accounts,
            "total": total,
            "limit": limit,
            "offset": offset,
        }


async def list_services() -> list[str]:
    async with get_async_session() as session:
        return await list_services_async(session)


async def has_service(service: str) -> bool:
    async with get_async_session() as session:
        return await service_exists_async(session, service)


async def get_account(service: str, email: str) -> dict[str, Any] | None:
    async with get_async_session() as session:
        return await get_account_by_email_async(session, service, email)


async def update_account_fields(service: str, email: str, **fields) -> bool:
    async with get_async_session() as session:
        updated = await update_account_async(session, service, email, fields)
        return updated > 0


async def add_account(
    service: str,
    email: str,
    api_key: str = "",
    password: str = "",
    totp_secret: str = "",
    app_password: str = "",
    source_email: str = "",
) -> bool:
    from src.core.account_record import AccountRecord
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

    async with get_async_session() as session:
        # Build ext_data for extension tables
        svc = service.upper()
        ext_data = None
        if svc == "GMAIL":
            ext_data = {"totp_secret": totp_secret, "app_password": app_password, "label": ""}
        elif svc == "ARTIFICIALANALYSIS":
            ext_data = {"api_key": api_key, "org_slug": ""}
        elif svc == "OPENROUTER":
            ext_data = {"api_key": api_key}
        elif svc in ("ELEVENLABS", "OLLAMA", "TESTMAIL"):
            ext_data = {"api_key": api_key}
        elif svc == "MAILOSAUR":
            ext_data = {"api_key": api_key, "server_id": ""}

        inserted = await insert_account_async(session, record, ext_data)

        # Auto-upsert mailbox for Gmail accounts with app_password
        if app_password and inserted:
            mailbox_email: str | None = None
            if clean_source_email and _parse_gmail(clean_source_email):
                mailbox_email = clean_source_email
            elif _parse_gmail(email):
                mailbox_email = normalize_gmail(email)
            if mailbox_email:
                await upsert_mailbox_async(
                    session,
                    mailbox_email,
                    app_password=app_password,
                    totp_secret=totp_secret,
                    disabled=False,
                )

        return inserted


async def remove_account(service: str, email: str) -> bool:
    async with get_async_session() as session:
        return await delete_account_async(session, service, email)


async def remove_disabled_accounts(service: str) -> int:
    async with get_async_session() as session:
        return await delete_disabled_accounts_async(session, service.upper())


async def create_service(name: str, has_registrar: bool = False) -> bool:
    async with get_async_session() as session:
        return await add_service_async(session, name, has_registrar)


async def destroy_service(name: str) -> bool:
    async with get_async_session() as session:
        return await delete_service_async(session, name)
