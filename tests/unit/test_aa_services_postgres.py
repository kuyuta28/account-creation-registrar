from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AA_REGISTRAR = ROOT / "src" / "services" / "artificialanalysis_ai" / "registrar.py"
AA_RUNNER = ROOT / "src" / "services" / "artificialanalysis_ai" / "runner.py"
AA_SESSION = ROOT / "src" / "services" / "artificialanalysis_ai" / "session.py"


def test_artificialanalysis_services_use_postgres_session_api():
    registrar_source = AA_REGISTRAR.read_text(encoding="utf-8")
    runner_source = AA_RUNNER.read_text(encoding="utf-8")
    session_source = AA_SESSION.read_text(encoding="utf-8")

    combined = "\n".join([registrar_source, runner_source, session_source])
    assert "save_session(email, context)" in combined
    assert "from common.database import update_account\n" not in registrar_source
    assert "from common.database import update_account," not in registrar_source
    assert "update_account(db_path" not in registrar_source
    assert "get_accounts_async" in runner_source
    assert "get_async_session" in runner_source
    assert "from common.database import get_accounts\n" not in runner_source
    assert "from common.database import get_accounts," not in runner_source
    assert "from src.core.storage import db_path" not in combined
    assert "init_db" not in runner_source
