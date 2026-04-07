"""
database/__init__.py — Public API re-exports.

Tất cả imports từ code ngoài phải dùng:
    from ...core.database import init_db, get_accounts, ...
"""
from __future__ import annotations

from ._migrations import init_db
from ._engine import _engines, _get_engine, _MailProvider
from ._services import (
    add_service,
    delete_service,
    get_distinct_services,
    service_exists,
)
from ._accounts import (
    bulk_insert,
    check_gmail_variations_availability,
    count_accounts,
    delete_account,
    delete_accounts,
    delete_disabled_service_accounts,
    get_account_by_email,
    get_accounts,
    get_used_gmail_variations,
    insert_account,
    update_account,
    update_accounts_bulk,
    upsert_account,
)
from ._mailboxes import (
    block_mailbox_for_service,
    delete_sms_phone,
    delete_mailbox_record,
    get_available_mailboxes_for_service,
    get_mailbox_google_auth_state,
    get_mailbox_record,
    get_mailboxes,
    get_sms_phones,
    get_service_blocks,
    is_mailbox_blocked_for_service,
    save_mailbox_google_auth_state,
    unblock_mailbox_for_service,
    upsert_sms_phone,
    upsert_mailbox_record,
)
from ._providers import (
    cycle_provider_tag,
    get_all_providers_with_tags,
    get_mail_providers,
    get_provider_domains,
    set_provider_domain_tags,
    update_provider,
    upsert_mail_provider,
)

__all__ = [
    # migrations
    "init_db",
    # services
    "add_service", "delete_service", "get_distinct_services", "service_exists",
    # accounts
    "bulk_insert", "check_gmail_variations_availability", "count_accounts",
    "delete_account", "delete_accounts", "delete_disabled_service_accounts",
    "get_account_by_email", "get_accounts", "get_used_gmail_variations",
    "insert_account", "update_account", "update_accounts_bulk", "upsert_account",
    # mailboxes
    "block_mailbox_for_service", "delete_mailbox_record",
    "delete_sms_phone",
    "get_available_mailboxes_for_service", "get_mailbox_google_auth_state",
    "get_mailbox_record", "get_mailboxes", "get_sms_phones", "get_service_blocks",
    "is_mailbox_blocked_for_service", "save_mailbox_google_auth_state",
    "unblock_mailbox_for_service", "upsert_mailbox_record", "upsert_sms_phone",
    # providers
    "cycle_provider_tag", "get_all_providers_with_tags", "get_mail_providers",
    "get_provider_domains", "set_provider_domain_tags", "update_provider",
    "upsert_mail_provider",
]
