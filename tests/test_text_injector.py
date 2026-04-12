"""Tests for src/shared/text_injector.py"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Patch AppKit/Quartz before importing so the module loads on non-macOS CI
_APPKIT_MOCK = MagicMock()
_QUARTZ_MOCK = MagicMock()

with patch.dict("sys.modules", {"AppKit": _APPKIT_MOCK, "Quartz": _QUARTZ_MOCK}):
    from src.shared.text_injector import _is_pasteable, inject  # noqa: E402


class TestIsPasteable:
    def test_empty_app_name_is_pasteable(self):
        assert _is_pasteable("") is True

    def test_unknown_app_is_pasteable(self):
        assert _is_pasteable("Cursor") is True
        assert _is_pasteable("Slack") is True
        assert _is_pasteable("Notes") is True

    def test_finder_not_pasteable(self):
        assert _is_pasteable("Finder") is False

    def test_system_settings_not_pasteable(self):
        assert _is_pasteable("System Settings") is False
        assert _is_pasteable("System Preferences") is False

    def test_spotlight_not_pasteable(self):
        assert _is_pasteable("Spotlight") is False

    def test_case_insensitive(self):
        assert _is_pasteable("finder") is False
        assert _is_pasteable("SYSTEM SETTINGS") is False


class TestInject:
    def test_empty_text_returns_false(self):
        with patch.dict("sys.modules", {"AppKit": _APPKIT_MOCK, "Quartz": _QUARTZ_MOCK}):
            from src.shared import text_injector
            success, reason = text_injector.inject("", "Notes")
        assert success is False
        assert "empty" in reason.lower()

    def test_non_pasteable_app_returns_false(self):
        with patch.dict("sys.modules", {"AppKit": _APPKIT_MOCK, "Quartz": _QUARTZ_MOCK}):
            from src.shared import text_injector
            success, reason = text_injector.inject("hello", "Finder")
        assert success is False
        assert "finder" in reason.lower()
