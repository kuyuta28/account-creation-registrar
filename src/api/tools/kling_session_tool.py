"""
kling_session_tool.py — Mở browser Playwright để capture Kling AI session sau login Google.

Chạy như subprocess độc lập (cần GUI để user login thủ công).
Usage: python -m src.api.tools.kling_session_tool [gmail_hint]
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))


async def main() -> None:
    gmail_hint = sys.argv[1] if len(sys.argv) > 1 else ""

    from src.config.settings import load_config
    from src.core.account_record import Repo, init_repo
    from src.services.klingai_com.registrar import save_session

    cfg = load_config()

    from src.core.logging import make_logger

    log = make_logger("kling-session", cfg.log, cfg.base_dir)

    def log_fn(msg: str) -> None:
        log.info(msg)
        print(msg)

    repo = Repo(base_dir=cfg.base_dir, auth_sync=cfg.auth_sync, cliproxy_sync=cfg.cliproxy_sync)
    init_repo(repo)

    record = await save_session(cfg, log_fn, repo, gmail_hint=gmail_hint)

    if record:
        print(f"\nDONE — Email: {record.email}")
    else:
        print("\nFAILED — Session không được lưu.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
