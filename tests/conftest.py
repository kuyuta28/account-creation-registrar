"""
conftest.py — Shared pytest fixtures cho toàn bộ test suite.

Design Patterns:
  - Factory fixtures: trả factory function thay vì object trực tiếp (flexible)
  - tmp_path scoped: mỗi test có tmpdir riêng (isolation)
  - real_db: SQLite thật trong tmpdir (không mock)
  - real_cfg: load_config() với tmpdir trống → pure defaults

Không mock IO ở đây — fixtures provide REAL implementations.
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path
from typing import Generator

import pytest

# Đảm bảo src/ importable
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))


# ── event loop ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop_policy():
    """Standard asyncio policy."""
    return asyncio.DefaultEventLoopPolicy()


# ── directories ───────────────────────────────────────────────────────────────

@pytest.fixture
def project_root() -> Path:
    return _ROOT


@pytest.fixture
def config_dir() -> Path:
    return _ROOT / "config"


# ── helpers inline (no unnecessary abstraction) ───────────────────────────────

def run_async(coro):
    """Run a coroutine in a NEW event loop (safe for sync test context)."""
    return asyncio.run(coro)


# ── real SQLite DB ─────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path) -> Generator[Path, None, None]:
    """Fresh SQLite database trong tmpdir — real SQLAlchemy engine."""
    from src.core.database import init_db, _engines

    db = tmp_path / "test.db"
    init_db(db)
    yield db

    # Cleanup: dispose engine để tránh WinError 32 khi xóa tmpdir
    key = str(db.resolve())
    engine = _engines.pop(key, None)
    if engine:
        engine.dispose()


# ── real AppConfig (defaults only, no yaml) ──────────────────────────────────

@pytest.fixture
def default_cfg():
    """AppConfig với tất cả giá trị default — không load yaml."""
    from src.config.settings import AppConfig
    return AppConfig()


# ── real AppConfig (từ config/ thật của project) ─────────────────────────────

@pytest.fixture(scope="session")
def real_cfg():
    """Load config từ config/ thật của project — dùng cho integration tests."""
    from src.config.settings import load_config
    return load_config(_ROOT / "config" / "config.yaml")


# ── sample AccountRecord factory ─────────────────────────────────────────────

@pytest.fixture
def make_account():
    """Factory tạo AccountRecord với overrides."""
    def _factory(**kwargs):
        from src.core.storage import AccountRecord
        defaults = dict(
            service="ELEVENLABS",
            email="test@example.com",
            password="P@ssw0rd!",
            api_key="sk_test123",
        )
        defaults.update(kwargs)
        return AccountRecord(**defaults)
    return _factory


# ── Repo fixture (real SQLite) ────────────────────────────────────────────────

@pytest.fixture
def tmp_repo(tmp_path, tmp_db):
    """Repo với real SQLite DB trong tmpdir."""
    from src.core.storage import Repo, init_repo
    repo = Repo(base_dir=tmp_path)
    init_repo(repo)
    return repo
