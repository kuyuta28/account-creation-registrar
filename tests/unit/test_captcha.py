"""
unit/test_captcha.py — Tests cho src/captcha/ + src/services/elevenlabs_io/captcha.py

Bao phủ:
  - capsolver.py: _detect_provider, _run_sync
  - elevenlabs captcha: _valid_coord, _area, _fmt_bbox, _find_challenge_bbox,
                        _execute_clicks, _click_verify, _ask_llm_action
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config.settings import AppConfig, CaptchaConfig


# ── capsolver._detect_provider ────────────────────────────────────────────────

class TestDetectProvider:
    def test_ezcaptcha_priority(self):
        from src.captcha.capsolver import _detect_provider
        name, key = _detect_provider("ez_key", "cap_key", "two_key")
        assert name == "ezcaptcha"
        assert key == "ez_key"

    def test_twocaptcha_second(self):
        from src.captcha.capsolver import _detect_provider
        name, key = _detect_provider("", "cap_key", "two_key")
        assert name == "2captcha"
        assert key == "two_key"

    def test_capsolver_last(self):
        from src.captcha.capsolver import _detect_provider
        name, key = _detect_provider("", "cap_key", "")
        assert name == "capsolver"
        assert key == "cap_key"

    def test_no_key_raises_runtime_error(self):
        from src.captcha.capsolver import _detect_provider
        with pytest.raises(RuntimeError):
            _detect_provider("", "", "")


# ── capsolver._run_sync ───────────────────────────────────────────────────────

class TestRunSync:
    def test_outside_event_loop(self):
        from src.captcha.capsolver import _run_sync

        async def _coro():
            return 42

        assert _run_sync(_coro()) == 42

    def test_inside_event_loop(self):
        """_run_sync từ TRONG event loop → thread pool, không deadlock."""
        from src.captcha.capsolver import _run_sync

        async def _inner():
            return "hello"

        async def _main():
            return _run_sync(_inner())

        assert asyncio.run(_main()) == "hello"

    def test_exception_propagates(self):
        from src.captcha.capsolver import _run_sync

        async def _fail():
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            _run_sync(_fail())


# ── elevenlabs captcha: pure functions ───────────────────────────────────────

class TestValidCoord:
    def _vc(self, pt):
        from src.services.elevenlabs_io.captcha import _valid_coord
        return _valid_coord(pt)

    def test_center(self):         assert self._vc({"x": 0.5, "y": 0.5}) is True
    def test_origin(self):         assert self._vc({"x": 0.0, "y": 0.0}) is True
    def test_max(self):            assert self._vc({"x": 1.0, "y": 1.0}) is True
    def test_x_over_1(self):       assert self._vc({"x": 1.01, "y": 0.5}) is False
    def test_y_negative(self):     assert self._vc({"x": 0.5, "y": -0.01}) is False
    def test_missing_x(self):      assert self._vc({"y": 0.5}) is False
    def test_missing_y(self):      assert self._vc({"x": 0.5}) is False
    def test_empty_dict(self):     assert self._vc({}) is False
    def test_not_dict(self):       assert self._vc([0.5, 0.5]) is False
    def test_string_values(self):  assert self._vc({"x": "0.5", "y": "0.5"}) is False


class TestArea:
    def test_normal(self):
        from src.services.elevenlabs_io.captcha import _area
        assert abs(_area({"width": 400, "height": 300}) - 120_000) < 0.001

    def test_zero_width(self):
        from src.services.elevenlabs_io.captcha import _area
        assert _area({"width": 0, "height": 300}) == 0


class TestFmtBbox:
    def test_contains_all_dimensions(self):
        from src.services.elevenlabs_io.captcha import _fmt_bbox
        result = _fmt_bbox({"x": 10, "y": 20, "width": 400, "height": 300})
        for expected in ("10", "20", "400", "300"):
            assert expected in result


class TestFindChallengeBbox:
    def _page(self, bboxes):
        page = AsyncMock()
        elements = []
        for b in bboxes:
            el = AsyncMock()
            el.bounding_box = AsyncMock(return_value=b)
            elements.append(el)
        page.query_selector_all = AsyncMock(return_value=elements)
        return page

    def _cap(self):
        return CaptchaConfig()

    def test_no_iframes_returns_none(self):
        from src.services.elevenlabs_io.captcha import _find_challenge_bbox
        assert asyncio.run(_find_challenge_bbox(self._page([]), self._cap())) is None

    def test_none_bounding_box_skipped(self):
        from src.services.elevenlabs_io.captcha import _find_challenge_bbox
        assert asyncio.run(_find_challenge_bbox(self._page([None]), self._cap())) is None

    def test_too_small_returns_none(self):
        from src.services.elevenlabs_io.captcha import _find_challenge_bbox
        assert asyncio.run(_find_challenge_bbox(
            self._page([{"x": 0, "y": 0, "width": 100, "height": 100}]),
            self._cap(),
        )) is None

    def test_negative_y_skipped(self):
        from src.services.elevenlabs_io.captcha import _find_challenge_bbox
        assert asyncio.run(_find_challenge_bbox(
            self._page([{"x": 0, "y": -5, "width": 400, "height": 300}]),
            self._cap(),
        )) is None

    def test_valid_iframe_returned(self):
        from src.services.elevenlabs_io.captcha import _find_challenge_bbox
        bbox = {"x": 0, "y": 10, "width": 400, "height": 300}
        assert asyncio.run(_find_challenge_bbox(self._page([bbox]), self._cap())) == bbox

    def test_returns_largest(self):
        from src.services.elevenlabs_io.captcha import _find_challenge_bbox
        small = {"x": 0, "y": 1, "width": 300, "height": 250}
        large = {"x": 50, "y": 0, "width": 600, "height": 500}
        assert asyncio.run(_find_challenge_bbox(self._page([small, large]), self._cap())) == large

    def test_exact_minimum_size_accepted(self):
        from src.services.elevenlabs_io.captcha import _find_challenge_bbox
        bbox = {"x": 0, "y": 0, "width": 300, "height": 250}
        assert asyncio.run(_find_challenge_bbox(self._page([bbox]), self._cap())) == bbox

    def test_one_below_min_width_rejected(self):
        from src.services.elevenlabs_io.captcha import _find_challenge_bbox
        bbox = {"x": 0, "y": 0, "width": 299, "height": 300}
        assert asyncio.run(_find_challenge_bbox(self._page([bbox]), self._cap())) is None


class TestExecuteClicks:
    def _deps(self, click_delay_ms=0):
        return AsyncMock(), CaptchaConfig(click_delay_ms=click_delay_ms), MagicMock()

    def test_empty_list_no_mouse_call(self):
        from src.services.elevenlabs_io.captcha import _execute_clicks
        page, cap, logger = self._deps()
        asyncio.run(_execute_clicks(page, {"x": 0, "y": 0, "width": 400, "height": 300}, [], cap, logger))
        page.mouse.click.assert_not_called()

    def test_single_click_absolute_coords(self):
        from src.services.elevenlabs_io.captcha import _execute_clicks
        page, cap, logger = self._deps()
        bbox = {"x": 100, "y": 50, "width": 400, "height": 300}
        asyncio.run(_execute_clicks(page, bbox, [{"x": 0.5, "y": 0.5}], cap, logger))
        # abs: 100 + 0.5*400=300, 50 + 0.5*300=200
        page.mouse.click.assert_called_once_with(300.0, 200.0)

    def test_multiple_clicks_correct_count(self):
        from src.services.elevenlabs_io.captcha import _execute_clicks
        page, cap, logger = self._deps()
        bbox = {"x": 0, "y": 0, "width": 200, "height": 200}
        clicks = [{"x": 0.25, "y": 0.25}, {"x": 0.75, "y": 0.75}]
        asyncio.run(_execute_clicks(page, bbox, clicks, cap, logger))
        assert page.mouse.click.call_count == 2
        page.mouse.click.assert_any_call(50.0, 50.0)
        page.mouse.click.assert_any_call(150.0, 150.0)

    def test_top_left_click(self):
        from src.services.elevenlabs_io.captcha import _execute_clicks
        page, cap, logger = self._deps()
        bbox = {"x": 0, "y": 0, "width": 400, "height": 300}
        asyncio.run(_execute_clicks(page, bbox, [{"x": 0.0, "y": 0.0}], cap, logger))
        page.mouse.click.assert_called_once_with(0.0, 0.0)


class TestClickVerify:
    def _bbox(self):
        return {"x": 0, "y": 0, "width": 400, "height": 300}

    def test_with_btn_uses_llm_coords(self):
        from src.services.elevenlabs_io.captcha import _click_verify
        page, logger = AsyncMock(), MagicMock()
        asyncio.run(_click_verify(page, self._bbox(), {"x": 0.85, "y": 0.95}, logger))
        page.mouse.click.assert_called_once_with(340.0, 285.0)

    def test_without_btn_uses_fallback(self):
        from src.services.elevenlabs_io.captcha import _click_verify
        page, logger = AsyncMock(), MagicMock()
        asyncio.run(_click_verify(page, self._bbox(), None, logger))
        page.mouse.click.assert_called_once_with(328.0, 285.0)  # 0.82*400=328, 0.95*300=285

    def test_with_btn_offset_bbox(self):
        from src.services.elevenlabs_io.captcha import _click_verify
        page, logger = AsyncMock(), MagicMock()
        bbox = {"x": 100, "y": 50, "width": 200, "height": 100}
        asyncio.run(_click_verify(page, bbox, {"x": 0.5, "y": 0.5}, logger))
        page.mouse.click.assert_called_once_with(200.0, 100.0)  # 100+0.5*200, 50+0.5*100


class TestAskLLMAction:
    """_ask_llm_action — mocked LLM, test được JSON parsing."""

    def _cfg(self):
        return AppConfig()

    def _resp(self, content: str):
        m = MagicMock()
        m.choices[0].message.content = content
        return m

    @patch("src.services.elevenlabs_io.captcha._make_llm_client")
    def test_click_response_parsed(self, mk):
        from src.services.elevenlabs_io.captcha import _ask_llm_action
        mk.return_value.chat.completions.create = AsyncMock(return_value=self._resp(
            '{"type": "click", "clicks": [{"x": 0.3, "y": 0.4}]}'))
        r = asyncio.run(_ask_llm_action("b64", self._cfg(), MagicMock()))
        assert r["type"] == "click"
        assert len(r["clicks"]) == 1
        assert abs(r["clicks"][0]["x"] - 0.3) < 0.001

    @patch("src.services.elevenlabs_io.captcha._make_llm_client")
    def test_drag_response_parsed(self, mk):
        from src.services.elevenlabs_io.captcha import _ask_llm_action
        mk.return_value.chat.completions.create = AsyncMock(return_value=self._resp(
            '{"type": "drag", "drags": [{"from": {"x": 0.8, "y": 0.5}, "to": {"x": 0.3, "y": 0.5}}]}'))
        r = asyncio.run(_ask_llm_action("b64", self._cfg(), MagicMock()))
        assert r["type"] == "drag"
        assert len(r["drags"]) == 1

    @patch("src.services.elevenlabs_io.captcha._make_llm_client")
    def test_no_json_returns_empty_clicks(self, mk):
        from src.services.elevenlabs_io.captcha import _ask_llm_action
        mk.return_value.chat.completions.create = AsyncMock(return_value=self._resp("I cannot help with that."))
        r = asyncio.run(_ask_llm_action("b64", self._cfg(), MagicMock()))
        assert r["type"] == "click"
        assert r["clicks"] == []

    @patch("src.services.elevenlabs_io.captcha._make_llm_client")
    def test_out_of_range_click_filtered(self, mk):
        from src.services.elevenlabs_io.captcha import _ask_llm_action
        mk.return_value.chat.completions.create = AsyncMock(return_value=self._resp(
            '{"type": "click", "clicks": [{"x": 1.5, "y": 0.5}, {"x": 0.3, "y": 0.4}]}'))
        r = asyncio.run(_ask_llm_action("b64", self._cfg(), MagicMock()))
        assert len(r["clicks"]) == 1
        assert abs(r["clicks"][0]["x"] - 0.3) < 0.001

    @patch("src.services.elevenlabs_io.captcha._make_llm_client")
    def test_invalid_drag_to_coord_filtered(self, mk):
        from src.services.elevenlabs_io.captcha import _ask_llm_action
        mk.return_value.chat.completions.create = AsyncMock(return_value=self._resp(
            '{"type": "drag", "drags": ['
            '{"from": {"x": 0.8, "y": 0.5}, "to": {"x": 1.5, "y": 0.5}},'
            '{"from": {"x": 0.2, "y": 0.3}, "to": {"x": 0.6, "y": 0.7}}'
            ']}'))
        r = asyncio.run(_ask_llm_action("b64", self._cfg(), MagicMock()))
        assert len(r["drags"]) == 1

    @patch("src.services.elevenlabs_io.captcha._make_llm_client")
    def test_llm_exception_returns_none(self, mk):
        from src.services.elevenlabs_io.captcha import _ask_llm_action
        mk.return_value.chat.completions.create = AsyncMock(side_effect=Exception("timeout"))
        r = asyncio.run(_ask_llm_action("b64", self._cfg(), MagicMock()))
        assert r is None

    @patch("src.services.elevenlabs_io.captcha._make_llm_client")
    def test_missing_type_defaults_to_click(self, mk):
        from src.services.elevenlabs_io.captcha import _ask_llm_action
        mk.return_value.chat.completions.create = AsyncMock(return_value=self._resp(
            '{"clicks": [{"x": 0.5, "y": 0.5}]}'))
        r = asyncio.run(_ask_llm_action("b64", self._cfg(), MagicMock()))
        assert r["type"] == "click"

    @patch("src.services.elevenlabs_io.captcha._make_llm_client")
    def test_json_wrapped_in_markdown_fences_parsed(self, mk):
        from src.services.elevenlabs_io.captcha import _ask_llm_action
        mk.return_value.chat.completions.create = AsyncMock(return_value=self._resp(
            '```json\n{"type": "click", "clicks": [{"x": 0.5, "y": 0.5}]}\n```'))
        r = asyncio.run(_ask_llm_action("b64", self._cfg(), MagicMock()))
        assert r["type"] == "click"
        assert len(r["clicks"]) == 1

    @patch("src.services.elevenlabs_io.captcha._make_llm_client")
    def test_all_drag_coords_invalid_returns_empty_drags(self, mk):
        from src.services.elevenlabs_io.captcha import _ask_llm_action
        mk.return_value.chat.completions.create = AsyncMock(return_value=self._resp(
            '{"type": "drag", "drags": [{"from": {"x": 2.0, "y": 0.5}, "to": {"x": 0.3, "y": 0.5}}]}'))
        r = asyncio.run(_ask_llm_action("b64", self._cfg(), MagicMock()))
        assert r["type"] == "drag"
        assert r["drags"] == []
