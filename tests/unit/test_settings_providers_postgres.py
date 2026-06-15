from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SETTINGS = ROOT / "src" / "config" / "settings.py"


def test_settings_do_not_load_mail_providers_from_sqlite():
    source = SETTINGS.read_text(encoding="utf-8")

    assert "from common.database import get_mail_providers\n" not in source
    assert "from common.database import get_mail_providers," not in source
    assert "upsert_mail_provider" not in source
    assert "except Exception:\n            return ()" not in source
    assert "providers_for(self" not in source
