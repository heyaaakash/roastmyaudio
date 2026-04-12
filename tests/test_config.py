"""Tests for config/config.py — verifies all paths are project-local."""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(CONFIG_DIR))

import config  # noqa: E402


class TestProjectLocalPaths:
    def test_cache_dir_inside_project(self):
        assert str(config.CACHE_DIR).startswith(str(PROJECT_ROOT))

    def test_models_cache_inside_project(self):
        assert str(config.MODELS_CACHE_DIR).startswith(str(PROJECT_ROOT))

    def test_huggingface_cache_inside_project(self):
        assert str(config.HUGGINGFACE_CACHE_DIR).startswith(str(PROJECT_ROOT))

    def test_data_dir_inside_project(self):
        assert str(config.DATA_DIR).startswith(str(PROJECT_ROOT))

    def test_temp_uploads_inside_project(self):
        assert str(config.TEMP_UPLOADS_DIR).startswith(str(PROJECT_ROOT))

    def test_history_path_inside_project(self):
        assert str(config.HISTORY_PATH).startswith(str(PROJECT_ROOT))

    def test_dictionary_path_inside_project(self):
        assert str(config.DICTIONARY_PATH).startswith(str(PROJECT_ROOT))


class TestEnvironmentVariables:
    def test_hf_home_set_to_local_cache(self):
        assert os.environ.get("HF_HOME", "").startswith(str(PROJECT_ROOT))

    def test_xdg_cache_home_set_to_local_cache(self):
        assert os.environ.get("XDG_CACHE_HOME", "").startswith(str(PROJECT_ROOT))


class TestDefaults:
    def test_default_model_defined(self):
        assert config.DEFAULT_MODEL

    def test_sample_rate_is_16000(self):
        assert config.SAMPLE_RATE == 16_000

    def test_channels_is_mono(self):
        assert config.CHANNELS == 1
