"""mail/providers/__init__.py"""
from .mail_tm import create_mailbox as mail_tm_create, get_messages as mail_tm_get, get_message_body as mail_tm_body, wait_for_message as mail_tm_wait
from .testmail_app import create_mailbox as testmail_create, get_messages as testmail_get, wait_for_message as testmail_wait
from .guerrillamail_com import create_mailbox as guerrillamail_create, get_messages as guerrillamail_get, get_message_body as guerrillamail_body, wait_for_message as guerrillamail_wait
from .mailosaur_com import create_mailbox as mailosaur_create, get_messages as mailosaur_get, get_message_body as mailosaur_body, wait_for_message as mailosaur_wait
from common.database import get_mail_providers_async
from common.database._engine import get_async_session


async def load_provider_connections(service: str = "") -> tuple[str, ...]:
    async with get_async_session() as session:
        rows = await get_mail_providers_async(
            session,
            service_tag=service.lower() if service else None,
        )
    return tuple(row["connection_str"] for row in rows)


__all__ = [
    "guerrillamail_body",
    "guerrillamail_create",
    "guerrillamail_get",
    "guerrillamail_wait",
    "mail_tm_body",
    "mail_tm_create",
    "mail_tm_get",
    "mail_tm_wait",
    "mailosaur_body",
    "mailosaur_create",
    "mailosaur_get",
    "mailosaur_wait",
    "load_provider_connections",
    "testmail_create",
    "testmail_get",
    "testmail_wait",
]

