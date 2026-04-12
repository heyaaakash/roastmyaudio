"""Tests for src/shared/settings.py"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.shared.settings import DEFAULTS, load, save, get, set as settings_set  # noqa: E402


def _temp_settings_path(tmp_path: Path) -> Path:
    return tmp_path / "settings.json"


class TestLoad:
    def test_returns_defaults_when_no_file(self, tmp_path):
        with patch("src.shared.settings.SETTINGS_PATH", _temp_settings_path(tmp_path)):
            result = load()
        assert result == DEFAULTS

    def test_loads_saved_values(self, tmp_path):
        path = _temp_settings_path(tmp_path)
        path.write_text(json.dumps({"model": "large-v3", "language": "es"}))
        with patch("src.shared.settings.SETTINGS_PATH", path):
            result = load()
        assert result["model"] == "large-v3"
        assert result["language"] == "es"

    def test_merges_missing_keys_with_defaults(self, tmp_path):
        path = _temp_settings_path(tmp_path)
        path.write_text(json.dumps({"model": "tiny"}))
        with patch("src.shared.settings.SETTINGS_PATH", path):
            result = load()
        # Keys not in the file should get default values
        assert "language" in result
        assert result["language"] == DEFAULTS["language"]

    def test_ignores_unknown_keys(self, tmp_path):
        path = _temp_settings_path(tmp_path)
        path.write_text(json.dumps({"model": "tiny", "unknown_key": "bad"}))
        with patch("src.shared.settings.SETTINGS_PATH", path):
            result = load()
        assert "unknown_key" not in result

    def test_returns_defaults_on_corrupt_file(self, tmp_path):
        path = _temp_settings_path(tmp_path)
        path.write_text("not valid json {{{")
        with patch("src.shared.settings.SETTINGS_PATH", path):
            result = load()
        assert result == DEFAULTS


class TestSave:
    def test_persists_settings(self, tmp_path):
        path = _temp_settings_path(tmp_path)
        with patch("src.shared.settings.SETTINGS_PATH", path):
            save({"model": "base", **DEFAULTS})
        stored = json.loads(path.read_text())
        assert stored["model"] == "base"

    def test_only_saves_known_keys(self, tmp_path):
        path = _temp_settings_path(tmp_path)
        data = dict(DEFAULTS)
        data["secret_key"] = "should_not_be_saved"
        with patch("src.shared.settings.SETTINGS_PATH", path):
            save(data)
        stored = json.loads(path.read_text())
        assert "secret_key" not in stored


class TestGetSet:
    def test_get_returns_default(self, tmp_path):
        with patch("src.shared.settings.SETTINGS_PATH", _temp_settings_path(tmp_path)):
            assert get("model") == DEFAULTS["model"]

    def test_set_persists_value(self, tmp_path):
        path = _temp_settings_path(tmp_path)
        with patch("src.shared.settings.SETTINGS_PATH", path):
            settings_set("model", "small")
            assert get("model") == "small"

    def test_set_unknown_key_raises(self, tmp_path):
        import pytest
        with patch("src.shared.settings.SETTINGS_PATH", _temp_settings_path(tmp_path)):
            with pytest.raises(KeyError):
                settings_set("nonexistent_key", "value")
