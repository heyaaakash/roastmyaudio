"""Tests for src/apps/macos/hud_overlay.py"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.apps.macos.hud_overlay import (  # noqa: E402
    WAVEFORM_BAR_COUNT,
    WAVEFORM_BAR_GAP,
    WAVEFORM_BAR_WIDTH,
    DictationOverlay,
    _bar_x_positions,
    _normalize_audio_level,
)


# ---------------------------------------------------------------------------
# _normalize_audio_level
# ---------------------------------------------------------------------------
class TestNormalizeAudioLevel:
    def test_zero_is_zero(self):
        assert _normalize_audio_level(0.0) == 0.0

    def test_negative_clamps_to_zero(self):
        assert _normalize_audio_level(-0.5) == 0.0

    def test_full_rms_saturates_to_one(self):
        assert _normalize_audio_level(0.08) == 1.0
        assert _normalize_audio_level(0.20) == 1.0

    def test_curve_uses_sqrt(self):
        # 0.02 / 0.08 == 0.25 -> sqrt -> 0.5
        assert _normalize_audio_level(0.02) == 0.25 ** 0.5
        # 0.005 / 0.08 == 0.0625 -> sqrt -> 0.25
        assert _normalize_audio_level(0.005) == 0.0625 ** 0.5

    def test_monotonic_nondecreasing(self):
        levels = [0.0, 0.005, 0.01, 0.02, 0.04, 0.08, 0.2]
        out = [_normalize_audio_level(x) for x in levels]
        assert all(out[i] <= out[i + 1] for i in range(len(out) - 1))


# ---------------------------------------------------------------------------
# _bar_x_positions
# ---------------------------------------------------------------------------
class TestBarXPositions:
    def test_count_matches(self):
        xs = _bar_x_positions(5, 5.0, 5.0, 72.0)
        assert len(xs) == 5

    def test_group_is_centered(self):
        count, w, gap, W = 5, 5.0, 5.0, 72.0
        xs = _bar_x_positions(count, w, gap, W)
        total = count * w + (count - 1) * gap
        assert abs(xs[0] - (W - total) / 2.0) < 1e-9
        assert abs(xs[-1] + w - (xs[0] + total)) < 1e-9

    def test_constant_spacing_matches_globals(self):
        xs = _bar_x_positions(
            WAVEFORM_BAR_COUNT, WAVEFORM_BAR_WIDTH, WAVEFORM_BAR_GAP, 72.0
        )
        step = WAVEFORM_BAR_WIDTH + WAVEFORM_BAR_GAP
        assert all(abs((xs[i + 1] - xs[i]) - step) < 1e-9 for i in range(len(xs) - 1))


# ---------------------------------------------------------------------------
# DictationOverlay no-op behaviour when AppKit is unavailable
# ---------------------------------------------------------------------------
class TestOverlayUnavailable:
    def test_construct_without_appkit_has_no_window(self):
        with patch("src.apps.macos.hud_overlay.APPKIT_AVAILABLE", False):
            ov = DictationOverlay()
        assert ov.window is None

    def test_public_api_is_safe_noop_without_appkit(self):
        with patch("src.apps.macos.hud_overlay.APPKIT_AVAILABLE", False):
            ov = DictationOverlay()
        ov.show()
        ov.hide()
        ov.set_title("Dictating · base")
        ov.set_preview_text("hello world")
        ov.set_audio_level(0.6)
        ov.reset_waveform()
        assert ov.window is None
        assert ov._waveform is None
