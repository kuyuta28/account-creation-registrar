from __future__ import annotations

from unittest.mock import patch

import pytest

from src.config.settings import AppConfig, DatabaseConfig


@pytest.mark.skipif(
    not __import__("os").getenv("DATABASE_URL"),
    reason="DATABASE_URL is required for PostgreSQL bootstrap smoke verification",
)
def test_app_config_initializes_async_database_from_database_url():
    database_url = __import__("os").environ["DATABASE_URL"]
    cfg = AppConfig(database=DatabaseConfig(database_url=database_url))

    with patch("common.database._engine.init_async_db") as init_async_db:
        cfg.init_async_db()

    init_async_db.assert_called_once_with(database_url)
