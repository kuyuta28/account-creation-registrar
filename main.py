"""
main.py - Entry point. Delegates entirely to src/cli/menu.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "common" / "src"))

# Thêm zc-zhangchen/any-auto-register vào sys.path để dùng trực tiếp
_zc_path = Path(__file__).parent / "any-auto-register"
if _zc_path.exists():
    sys.path.insert(0, str(_zc_path))

from src.config.settings import load_config
from src.core.logger import install_tee
from common.context import init_app_context
from src.api.services.job_manager import JobManager

_cfg = load_config()
install_tee(_cfg.base_dir, _cfg.log.all_log)

# Init JobManager with config limits
job_state = JobManager(
    max_jobs=_cfg.registration.max_jobs,
    max_workers=_cfg.registration.max_workers,
)
init_app_context(config=_cfg, db_engine=None, job_state=job_state)

from src.cli.menu import main

if __name__ == "__main__":
    main()
