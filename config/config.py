"""
Project configuration module.
Centralizes all paths and settings for the Whisper project.
All cache, models, and data are stored locally within the project.
"""

import os
from pathlib import Path

# Project root is two directories up from this config file
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Local cache directories (all within the project)
CACHE_DIR = PROJECT_ROOT / "cache"
MODELS_CACHE_DIR = CACHE_DIR / "models"
HUGGINGFACE_CACHE_DIR = CACHE_DIR / "cache"

# Data directories
DATA_DIR = PROJECT_ROOT / "data"
TEMP_UPLOADS_DIR = DATA_DIR / "temp_uploads"
RUNTIME_DIR = DATA_DIR / "runtime"

# Create directories if they don't exist
for directory in [CACHE_DIR, MODELS_CACHE_DIR, HUGGINGFACE_CACHE_DIR,
                  TEMP_UPLOADS_DIR, RUNTIME_DIR]:
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
DEFAULT_MODEL = "turbo"
SAMPLE_RATE = 16000
CHANNELS = 1

# Ollama settings for LLM cleanup
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = "llama3.2:1b"

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
FLASK_PORT = 5000

# Links
HOME_URL = "https://github.com/openai/whisper"
UPDATES_URL = "https://github.com/openai/whisper/releases"
HELP_CENTER_URL = "https://github.com/openai/whisper#readme"
SUPPORT_URL = "https://github.com/openai/whisper/discussions"
FEEDBACK_URL = "https://github.com/openai/whisper/issues"

def print_config():
    """Print current configuration for debugging."""
    print(f"PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"CACHE_DIR: {CACHE_DIR}")
    print(f"MODELS_CACHE_DIR: {MODELS_CACHE_DIR}")
    print(f"HUGGINGFACE_CACHE_DIR: {HUGGINGFACE_CACHE_DIR}")
    print(f"TEMP_UPLOADS_DIR: {TEMP_UPLOADS_DIR}")
    print(f"RUNTIME_DIR: {RUNTIME_DIR}")
