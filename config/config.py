"""
Project configuration module.
Centralizes all paths and settings for the Whisper project.
Desktop storage is stable across installations; web development stays project-local.
"""

import os
import sys
from pathlib import Path

# Frozen resources are read-only; user storage always lives outside the bundle.
PROJECT_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
DESKTOP_MODE = os.environ.get("RMA_DESKTOP") == "1"
DATA_DIR = Path(os.environ.get("RMA_DATA_HOME", str(
    Path.home() / "Library/Application Support/RoastMyAudio" if DESKTOP_MODE else PROJECT_ROOT / "data"
))).expanduser()
CACHE_DIR = Path(os.environ.get("RMA_CACHE_HOME", str(
    Path.home() / "Library/Caches/RoastMyAudio" if DESKTOP_MODE else PROJECT_ROOT / "cache"
))).expanduser()
MODELS_CACHE_DIR = CACHE_DIR / "models"
HUGGINGFACE_CACHE_DIR = CACHE_DIR / "huggingface"
LLM_CACHE_DIR = CACHE_DIR / "llm"
TEMP_UPLOADS_DIR = DATA_DIR / "temp_uploads"
RUNTIME_DIR = DATA_DIR / "runtime"
RECORDINGS_DIR = DATA_DIR / "recordings"

# Create directories if they don't exist
for directory in [CACHE_DIR, MODELS_CACHE_DIR, HUGGINGFACE_CACHE_DIR, LLM_CACHE_DIR,
                  TEMP_UPLOADS_DIR, RUNTIME_DIR, RECORDINGS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Environment variables for cache locations
# These override default behavior to use our local cache
os.environ['HOME_CACHE_DIR'] = str(MODELS_CACHE_DIR)
os.environ['XDG_CACHE_HOME'] = str(HUGGINGFACE_CACHE_DIR)

# Whisper/HuggingFace model cache
os.environ['HF_HOME'] = str(HUGGINGFACE_CACHE_DIR)
HF_HOME = HUGGINGFACE_CACHE_DIR

# Settings file
SETTINGS_PATH = DATA_DIR / "settings.json"

# Dictionary and history storage (moved from ~/.wispr_local to project)
DICTIONARY_PATH = DATA_DIR / "dictionary.json"
HISTORY_PATH = DATA_DIR / "history.json"
LAST_RECORDING_PATH = RUNTIME_DIR / "last_recording.wav"
LAST_PROCESSED_PATH = RUNTIME_DIR / "last_processed.txt"

# Application settings
DEFAULT_MODEL = os.environ.get("WHISPER_MODEL", "base")
SAMPLE_RATE = 16000
CHANNELS = 1

# Embedded local LLM settings (Metal accelerated on Apple Silicon)
DEFAULT_LLM_MODEL = os.environ.get("LLM_MODEL", "qwen2.5-0.5b")
SUPPORTED_LLM_MODELS = {
    "qwen2.5-0.5b": {
        "repo_id": "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
        "filename": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "display_name": "Qwen 2.5 0.5B (Fast & Accurate)",
        "prompt_format": "chatml",
    },
    "smollm2-360m": {
        "repo_id": "HuggingFaceTB/SmolLM2-360M-Instruct-GGUF",
        "filename": "smollm2-360m-instruct-q4_k_m.gguf",
        "display_name": "SmolLM2 360M (Ultra-fast Fallback)",
        "prompt_format": "chatml",
    },
}

# macOS settings
FALLBACK_HOLD_HOTKEY = "Ctrl+Option+D"
LIVE_PREVIEW_INTERVAL_SEC = 0.6
LIVE_PREVIEW_WINDOW_SEC = 2.0
LIVE_PREVIEW_MIN_AUDIO_SEC = 0.45
LIVE_PREVIEW_WORD_LIMIT = 6
LIVE_PREVIEW_MODEL_PREFERENCE = ("tiny.en", "tiny", "base.en", "base")
PTT_STATE_POLL_SEC = 0.12
PTT_MAX_HOLD_SEC = 300  # Auto-stop after 5 minutes if stuck
FAST_COMMIT_CHUNK_SEC = 0.35
FAST_COMMIT_POLL_SEC = 0.1
FAST_COMMIT_MIN_TAIL_SEC = 0.1
SHORT_UTTERANCE_FAST_PATH_SEC = 0.8
AUDIO_NORM_TARGET_RMS = 0.15

# Web app settings
FLASK_HOST = "127.0.0.1"
FLASK_PORT = int(os.environ.get("FLASK_PORT", "5000"))

# Links
HOME_URL = "https://github.com/heyaaakash/roastmyaudio"
UPDATES_URL = "https://github.com/heyaaakash/roastmyaudio/releases"
HELP_CENTER_URL = "https://github.com/heyaaakash/roastmyaudio/blob/main/docs/INSTALLATION.md"
SUPPORT_URL = "https://github.com/heyaaakash/roastmyaudio/issues"
FEEDBACK_URL = "https://github.com/heyaaakash/roastmyaudio/issues"

def print_config():
    """Print current configuration for debugging."""
    print(f"PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"CACHE_DIR: {CACHE_DIR}")
    print(f"MODELS_CACHE_DIR: {MODELS_CACHE_DIR}")
    print(f"HUGGINGFACE_CACHE_DIR: {HUGGINGFACE_CACHE_DIR}")
    print(f"TEMP_UPLOADS_DIR: {TEMP_UPLOADS_DIR}")
    print(f"RUNTIME_DIR: {RUNTIME_DIR}")
