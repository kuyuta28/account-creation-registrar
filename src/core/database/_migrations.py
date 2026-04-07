"""
database/_migrations.py — DB schema migrations + seeding.
All functions are idempotent — safe to call on every startup.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ._engine import (
    _Account, _Base, _MailProvider, _Service,
    _get_engine, _now,
)


# ── Column migration helpers ───────────────────────────────────────────────────

def _migrate_columns(engine) -> None:
    """Thêm columns mới nếu chưa tồn tại."""
    new_cols = [
        ("check_status",  "TEXT NOT NULL DEFAULT ''"),
        ("quota_pct",     "TEXT NOT NULL DEFAULT ''"),
        ("last_checked",  "TEXT NOT NULL DEFAULT ''"),
        ("last_error",    "TEXT NOT NULL DEFAULT ''"),
        ("session_state", "TEXT NOT NULL DEFAULT ''"),
        ("totp_secret",   "TEXT NOT NULL DEFAULT ''"),
        ("app_password",  "TEXT NOT NULL DEFAULT ''"),
        ("source_email",  "TEXT NOT NULL DEFAULT ''"),
        ("label",         "TEXT NOT NULL DEFAULT ''"),
    ]
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(accounts)"))
        existing = {row[1] for row in result}
        for col_name, col_def in new_cols:
            if col_name not in existing:
                conn.execute(text(f"ALTER TABLE accounts ADD COLUMN {col_name} {col_def}"))
        conn.commit()


def _migrate_mailboxes_to_accounts(engine) -> None:
    """
    One-time migration: copy data từ bảng mailboxes cũ → accounts(service='GMAIL').
    Sau đó DROP bảng mailboxes. Idempotent.
    """
    for col_def in [
        "password TEXT NOT NULL DEFAULT ''",
        "source_email TEXT NOT NULL DEFAULT ''",
        "google_auth_state TEXT NOT NULL DEFAULT ''",
    ]:
        try:
            with engine.connect() as _c:
                _c.execute(text(f"ALTER TABLE mailboxes ADD COLUMN {col_def}"))
                _c.commit()
        except Exception:  # noqa: BLE001 - SQLite ADD COLUMN: ignore duplicate column error
            pass

    with engine.connect() as conn:
        tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        if "mailboxes" not in tables:
            return

        conn.execute(text("""
            INSERT OR IGNORE INTO accounts
                (service, email, app_password, totp_secret, password, source_email,
                 session_state, disabled, created_at, updated_at,
                 api_key, credits, refresh_token, access_token, account_id, id_token,
                 expired, last_refresh, token_type, check_status, quota_pct, last_checked, last_error)
            SELECT
                'GMAIL', email, app_password, totp_secret, password, source_email,
                google_auth_state, disabled, created_at, updated_at,
                '', 0, '', '', '', '',
                '', '', '', '', '', '', ''
            FROM mailboxes
        """))
        conn.commit()
        conn.execute(text("DROP TABLE IF EXISTS mailboxes"))
        conn.execute(text("DROP INDEX IF EXISTS idx_mailboxes_disabled"))
        conn.commit()


def _normalize_provider_type(provider_domain: str, compound_key: str) -> str:
    short_map = {
        "mailslurp":        "mailslurp.com",
        "testmail":         "testmail.app",
        "mailtm":           "mail.tm",
        "mail.tm":          "mail.tm",
        "mailosaur":        "mailosaur.com",
        "mailosaur.com":    "mailosaur.com",
        "guerrillamail":    "guerrillamail.com",
        "guerrillamail.com":"guerrillamail.com",
    }
    if provider_domain in short_map:
        return short_map[provider_domain]
    if compound_key.startswith("mailslurp.com:"):
        return "mailslurp.com"
    if compound_key.startswith("testmail.app:"):
        return "testmail.app"
    if compound_key.startswith("mailosaur.com:"):
        return "mailosaur.com"
    if compound_key.startswith("guerrillamail.com"):
        return "guerrillamail.com"
    if compound_key.startswith("http"):
        return "mail.tm"
    return provider_domain


def _split_compound_key(provider_type: str, compound_key: str) -> tuple[str, str]:
    match provider_type:
        case "mailslurp.com":
            return compound_key.removeprefix("mailslurp.com:"), ""
        case "testmail.app":
            rest = compound_key.removeprefix("testmail.app:")
            ns, _, key = rest.partition(":")
            return key, ns
        case "mailosaur.com":
            rest = compound_key.removeprefix("mailosaur.com:")
            api_key, _, server_id = rest.partition(":")
            return api_key, server_id
        case "guerrillamail.com":
            return "", ""
        case _:
            return "", compound_key


def _migrate_provider_domain(engine) -> None:
    with engine.connect() as conn:
        tables = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}

        if "provider_service_tags" in tables and "provider_domain_tags" in tables:
            cols_pdt = {row[1] for row in conn.execute(text("PRAGMA table_info(provider_domain_tags)"))}
            domain_col = "provider_domain" if "provider_domain" in cols_pdt else "provider_type"
            conn.execute(text(f"""
                INSERT OR IGNORE INTO provider_domain_tags ({domain_col}, tag)
                SELECT DISTINCT mp.provider_domain, pst.tag
                FROM provider_service_tags pst
                JOIN mail_providers mp ON mp.id = pst.provider_id
            """))
            conn.execute(text("DROP TABLE IF EXISTS provider_service_tags"))

        if "mail_providers" in tables:
            cols = {row[1] for row in conn.execute(text("PRAGMA table_info(mail_providers)"))}
            if "provider_type" in cols and "provider_domain" not in cols and "server_id" not in cols:
                conn.execute(text("ALTER TABLE mail_providers RENAME COLUMN provider_type TO provider_domain"))

        conn.commit()


def _migrate_mail_provider_schema(engine) -> None:
    with engine.connect() as conn:
        tables = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        if "mail_providers" not in tables:
            return

        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(mail_providers)"))}
        already_done = "server_id" in cols and "provider_type" in cols and "provider_domain" not in cols
        if already_done:
            return

        old_domain_col = "provider_domain" if "provider_domain" in cols else "provider_type"
        rows = conn.execute(text(
            f"SELECT id, {old_domain_col}, api_key, label, disabled, fail_count, "
            "cooldown_until, last_used, created_at, updated_at FROM mail_providers"
        )).fetchall()

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mail_providers_new (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_type TEXT    NOT NULL,
                api_key       TEXT    NOT NULL DEFAULT '',
                server_id     TEXT    NOT NULL DEFAULT '',
                label         TEXT    NOT NULL DEFAULT '',
                disabled      BOOLEAN NOT NULL DEFAULT 0,
                fail_count    INTEGER NOT NULL DEFAULT 0,
                cooldown_until TEXT   NOT NULL DEFAULT '',
                last_used     TEXT    NOT NULL DEFAULT '',
                created_at    TEXT    NOT NULL,
                updated_at    TEXT    NOT NULL,
                UNIQUE(provider_type, api_key, server_id)
            )
        """))

        seen: set[tuple] = set()
        for row in rows:
            _id, old_domain, compound_key, label, disabled, fail_count, cooldown_until, last_used, created_at, updated_at = row
            ptype = _normalize_provider_type(old_domain or "", compound_key or "")
            raw_key, server_id = _split_compound_key(ptype, compound_key or "")
            dedup_key = (ptype, raw_key, server_id)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            conn.execute(text("""
                INSERT OR IGNORE INTO mail_providers_new
                (provider_type, api_key, server_id, label, disabled, fail_count,
                 cooldown_until, last_used, created_at, updated_at)
                VALUES (:pt, :key, :sid, :label, :disabled, :fc, :cu, :lu, :ca, :ua)
            """), {
                "pt": ptype, "key": raw_key, "sid": server_id,
                "label": label or "", "disabled": disabled or 0, "fc": fail_count or 0,
                "cu": cooldown_until or "", "lu": last_used or "",
                "ca": created_at or _now(), "ua": updated_at or _now(),
            })

        if "provider_domain_tags" in tables:
            tag_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(provider_domain_tags)"))}
            tag_domain_col = "provider_domain" if "provider_domain" in tag_cols else "provider_type"
            old_tags = conn.execute(text(f"SELECT {tag_domain_col}, tag FROM provider_domain_tags")).fetchall()

            conn.execute(text("DROP TABLE IF EXISTS provider_domain_tags"))
            conn.execute(text("""
                CREATE TABLE provider_domain_tags (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider_type TEXT    NOT NULL,
                    tag           TEXT    NOT NULL,
                    UNIQUE(provider_type, tag)
                )
            """))
            for old_domain, tag in old_tags:
                ptype = _normalize_provider_type(old_domain or "", "")
                if not ptype:
                    continue
                conn.execute(text("""
                    INSERT OR IGNORE INTO provider_domain_tags (provider_type, tag)
                    VALUES (:pt, :tag)
                """), {"pt": ptype, "tag": tag})

        conn.execute(text("DROP TABLE mail_providers"))
        conn.execute(text("ALTER TABLE mail_providers_new RENAME TO mail_providers"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_mail_providers_type ON mail_providers(provider_type)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_mail_providers_disabled ON mail_providers(disabled)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_domain_tag ON provider_domain_tags(tag)"))
        conn.commit()


def _seed_services_catalog(engine) -> None:
    from ...services.registry import SUPPORTED_SERVICES

    BUILTIN_NO_REGISTRAR: set[str] = {"GMAIL", "KLING"}

    with Session(engine) as s:
        account_services = set(
            s.execute(select(_Account.service).distinct().order_by(_Account.service)).scalars().all()
        )
        supported_upper = {sv.upper() for sv in SUPPORTED_SERVICES}
        seed_services = supported_upper | BUILTIN_NO_REGISTRAR | {sv.upper() for sv in account_services}

        for service in sorted(seed_services):
            s.execute(
                sqlite_insert(_Service)
                .values(name=service, has_registrar=service in supported_upper)
                .on_conflict_do_nothing(index_elements=["name"])
            )
        s.commit()


def _seed_default_providers(engine) -> None:
    now = _now()
    defaults = [
        {"provider_type": "mail.tm",          "server_id": "https://api.mail.tm", "label": "mail.tm"},
        {"provider_type": "guerrillamail.com", "server_id": "",                   "label": "Guerrilla Mail"},
    ]
    with Session(engine) as s:
        for d in defaults:
            s.execute(
                sqlite_insert(_MailProvider)
                .values(
                    provider_type=d["provider_type"],
                    api_key="",
                    server_id=d["server_id"],
                    label=d["label"],
                    disabled=False,
                    fail_count=0,
                    cooldown_until="",
                    last_used="",
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_nothing()
            )
        s.commit()


def init_db(db_path: Path) -> None:
    """Tạo bảng + index nếu chưa có (idempotent). Chạy migrations theo thứ tự."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = _get_engine(db_path)
    _Base.metadata.create_all(engine)
    _migrate_columns(engine)
    _migrate_provider_domain(engine)
    _migrate_mail_provider_schema(engine)
    _migrate_mailboxes_to_accounts(engine)
    _seed_services_catalog(engine)
    _seed_default_providers(engine)
