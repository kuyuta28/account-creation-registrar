"""
browser_tasks/ — Task registry cho Browser Gateway.

Mỗi task = 1 handler function (FP): nhận deps qua args, gọi module automation hiện có,
không mở browser trực tiếp (browser do gateway mở và truyền vào).

Thêm browser-task mới = tạo 1 file handler + import ở đây (side-effect register).
"""
from __future__ import annotations

from ._registry import get_task, list_tasks, register  # noqa: F401

# Import handlers để trigger @register side-effect.
# Phải import sau khi _registry sẵn sàng.
from . import login_gmail  # noqa: F401,E402
from . import relogin_aa  # noqa: F401,E402
from . import register_cloudflare  # noqa: F401,E402
from . import add_cf_to_9router  # noqa: F401,E402

__all__ = ["register", "get_task", "list_tasks"]
