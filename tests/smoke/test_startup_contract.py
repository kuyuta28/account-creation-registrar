from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import patch


def _fresh_server_module():
    sys.modules.pop("src.api.server", None)
    from src.config.settings import AllLogConfig, AppConfig, LogConfig

    cfg = AppConfig(base_dir=Path(__file__).resolve().parents[2], log=LogConfig(all_log=AllLogConfig(enabled=False)))
    with patch("src.config.settings.load_config", return_value=cfg):
        return importlib.import_module("src.api.server")


def test_fastapi_app_imports_with_v1_contract_routes():
    server = _fresh_server_module()
    paths = {route.path for route in server.app.routes}

    assert "/api/v1/health" in paths
    assert any(path.startswith("/api/v1/internal") for path in paths)
    assert server.app.docs_url == "/api/docs"
    assert server.app.openapi_url == "/api/openapi.json"
