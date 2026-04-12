"""
cli/menu.py — Interactive CLI menu + batch account-creation orchestration.

Application layer only: wires config / logger / repo / registrars / checkers.
No business logic lives here — every real action is delegated to a service.
"""
from __future__ import annotations

from ..config.settings import load_config
from src.core.storage import AccountRecord, Repo, init_repo, repo_sync_auth

_SEP = "=" * 60


# ── menu registry ─────────────────────────────────────────────────────────────

_MENU_LABELS = {
    "1": "Proton Mail",
    "2": "ElevenLabs + API key",
    "3": "Leonardo AI",
}


# ── pure display helpers ──────────────────────────────────────────────────────

def _ask_count() -> int:
    raw = input("How many accounts? [1]: ").strip()
    if not raw:
        return 1
    try:
        return max(1, int(raw))
    except ValueError:
        print("Invalid number — defaulting to 1.")
        return 1


def _print_result(i: int, total: int, record: AccountRecord) -> None:
    print(f"\n{_SEP}\n✅ [{i}/{total}] ACCOUNT CREATED SUCCESSFULLY!\n{_SEP}")
    print(f"  Email:    {record.email}")
    print(f"  Password: {record.password}")
    if record.api_key:
        print(f"  API Key:  {record.api_key}")
    print(_SEP)






# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    cfg  = load_config()
    repo = Repo(base_dir=cfg.base_dir, auth_sync=cfg.auth_sync, cliproxy_sync=cfg.cliproxy_sync)
    init_repo(repo)

    print(f"{_SEP}\n  ACCOUNT CREATION AUTOMATION\n{_SEP}")
    for key, label in _MENU_LABELS.items():
        print(f"  [{key}] {label}")
    print("  [5] Check ElevenLabs API key status")
    print("  [6] Check ChatGPT account status")
    print("  [7] Check ChatGPT quota (weekly usage%)")
    print("  [8] Sync exported auth files")
    print("  [0] Exit")
    print(_SEP)

    choice = input("Choose: ").strip()

    if choice == "0":
        print("Bye!")
        return
    if choice == "5":
        from ..checkers import elevenlabs as el_checker
        el_checker.main()
        return
    if choice == "6":
        from ..checkers import chatgpt as gpt_checker
        gpt_checker.main(save_refreshed=True, with_quota=False)
        return
    if choice == "7":
        from ..checkers import chatgpt as gpt_checker
        gpt_checker.main(save_refreshed=True, with_quota=True)
        return
    if choice == "8":
        synced = repo_sync_auth(repo)
        print(f"\nSynced {len(synced)} auth file(s) -> {cfg.auth_sync.target_dir}")
        return
    if choice not in _MENU_LABELS:
        print("Invalid choice.")
        return

    label = _MENU_LABELS[choice]
    total = _ask_count()
    print(f"\n{_SEP}\n  {label.upper()}  \u00d7{total}\n{_SEP}")

    from .runners import run_proton, run_elevenlabs, run_leonardo
    _runners = {"1": run_proton, "2": run_elevenlabs, "3": run_leonardo}
    _runners[choice](total)
