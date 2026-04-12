"""
Persistent user settings for WhisperFlow.

Settings are stored in data/settings.json inside the project directory.
All values have sensible defaults so the file is optional.
"""

import json
import sys
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
if str(CONFIG_DIR) not in sys.path:
    sys.path.insert(0, str(CONFIG_DIR))

from config import DATA_DIR  # noqa: E402

SETTINGS_PATH = DATA_DIR / "settings.json"

# Default values — the app works without a settings file
DEFAULTS: dict[str, Any] = {
    "model": "base",
    "language": "en",
    "language_label": "English",
    "hotkey": "fn",          # "fn" or "ctrl_option_d"
    "llm_enabled": True,
    "ollama_model": "llama3.2:1b",
    "device_id": None,       # None = system default microphone
}


def load() -> dict[str, Any]:
    """Load settings from disk, merging with defaults for missing keys."""
    if not SETTINGS_PATH.exists():
        return dict(DEFAULTS)
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        merged = dict(DEFAULTS)
        merged.update({k: v for k, v in data.items() if k in DEFAULTS})
        return merged
    except Exception:
        return dict(DEFAULTS)


def save(settings: dict[str, Any]) -> None:
    """Persist settings to disk. Only known keys are written."""
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    clean = {k: settings[k] for k in DEFAULTS if k in settings}
    SETTINGS_PATH.write_text(json.dumps(clean, indent=2), encoding="utf-8")


def get(key: str) -> Any:
    """Get a single setting value."""
    return load().get(key, DEFAULTS.get(key))


def set(key: str, value: Any) -> None:
    """Update and persist a single setting."""
    if key not in DEFAULTS:
        raise KeyError(f"Unknown setting '{key}'. Valid keys: {list(DEFAULTS)}")
    current = load()
    current[key] = value
    save(current)
