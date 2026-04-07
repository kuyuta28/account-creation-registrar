"""
unit/test_page_utils.py — Tests cho src/core/page_utils.py

Bao phủ:
  - safe_load (async)
  - safe_text (async)
  - dump_debug_html (async)
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile

from playwright.async_api import TimeoutError as PlaywrightTimeoutError


# ── safe_load ─────────────────────────────────────────────────────────────────

class TestSafeLoad:
    def _page(self, side_effect=None):
        page = AsyncMock()
        if side_effect:
            page.wait_for_load_state.side_effect = side_effect
        return page

    def test_calls_wait_for_load_state(self):
        from src.core.page_utils import safe_load
        page = self._page()
        asyncio.run(safe_load(page, 5000))
        page.wait_for_load_state.assert_called_once_with("domcontentloaded", timeout=5000)

    def test_timeout_silently_ignored(self):
        from src.core.page_utils import safe_load
        page = self._page(side_effect=TimeoutError("timed out"))
        # Không raise exception
        asyncio.run(safe_load(page, 1000))

    def test_playwright_timeout_silently_ignored(self):
        from src.core.page_utils import safe_load
        page = self._page(side_effect=PlaywrightTimeoutError("pw timeout"))
        asyncio.run(safe_load(page, 1000))

    def test_custom_timeout_passed(self):
        from src.core.page_utils import safe_load
        page = self._page()
        asyncio.run(safe_load(page, 12345))
        _, kwargs = page.wait_for_load_state.call_args
        assert kwargs.get("timeout") == 12345


# ── safe_text ─────────────────────────────────────────────────────────────────

class TestSafeText:
    def test_returns_body_text(self):
        from src.core.page_utils import safe_text
        page = AsyncMock()
        page.inner_text.return_value = "Hello World"
        result = asyncio.run(safe_text(page))
        assert result == "Hello World"
        page.inner_text.assert_called_once_with("body")

    def test_returns_empty_string_on_exception(self):
        from src.core.page_utils import safe_text
        page = AsyncMock()
        page.inner_text.side_effect = Exception("page crashed")
        result = asyncio.run(safe_text(page))
        assert result == ""

    def test_empty_page_returns_empty_string(self):
        from src.core.page_utils import safe_text
        page = AsyncMock()
        page.inner_text.return_value = ""
        result = asyncio.run(safe_text(page))
        assert result == ""


# ── dump_debug_html ───────────────────────────────────────────────────────────

class TestDumpDebugHtml:
    def test_creates_file_with_content(self):
        from src.core.page_utils import dump_debug_html

        page = AsyncMock()
        page.content.return_value = "<html><body>test</body></html>"

        with tempfile.TemporaryDirectory() as tmpdir:
            debug_dir = Path(tmpdir) / "debug"
            asyncio.run(dump_debug_html(page, "step1.html", debug_dir))
            output = debug_dir / "step1.html"
            assert output.exists()
            assert "<body>test</body>" in output.read_text()

    def test_creates_parent_directory(self):
        from src.core.page_utils import dump_debug_html

        page = AsyncMock()
        page.content.return_value = "<html/>"

        with tempfile.TemporaryDirectory() as tmpdir:
            deep_dir = Path(tmpdir) / "a" / "b" / "c"
            asyncio.run(dump_debug_html(page, "out.html", deep_dir))
            assert (deep_dir / "out.html").exists()

    def test_silent_on_exception(self):
        from src.core.page_utils import dump_debug_html

        page = AsyncMock()
        page.content.side_effect = Exception("crashed")

        with tempfile.TemporaryDirectory() as tmpdir:
            debug_dir = Path(tmpdir) / "debug"
            # Không raise exception
            asyncio.run(dump_debug_html(page, "out.html", debug_dir))

    def test_utf8_content_preserved(self):
        from src.core.page_utils import dump_debug_html

        page = AsyncMock()
        page.content.return_value = "<html>Tiếng Việt 🌟 한국어</html>"

        with tempfile.TemporaryDirectory() as tmpdir:
            debug_dir = Path(tmpdir)
            asyncio.run(dump_debug_html(page, "unicode.html", debug_dir))
            content = (debug_dir / "unicode.html").read_text(encoding="utf-8")
            assert "Tiếng Việt" in content
            assert "한국어" in content
