"""
Background model warmup for the macOS menu bar app.

Pre-loads Whisper models and warms up the Ollama LLM at startup so the
first push-to-talk invocation has no latency spike.
"""

import sys
import threading
from pathlib import Path
from typing import Callable, Optional

import numpy as np

# Path setup
PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = PROJECT_ROOT / "src"
CONFIG_DIR = PROJECT_ROOT / "config"
for _p in (str(PROJECT_ROOT), str(CONFIG_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from src.shared.llm_cleanup import warmup as ollama_warmup  # noqa: E402
from src.shared.transcriber import get_inference_lock, get_model_by_name  # noqa: E402


def load_models_async(on_complete: Optional[Callable] = None) -> None:
    """
    Pre-load the primary (base) and preview (tiny.en) Whisper models, plus
    warm up the Ollama LLM. Runs in a daemon thread so it never blocks the UI.

    Args:
        on_complete: Optional callback called on the thread when warmup finishes.
    """

    def _load():
        silence = np.zeros(16_000, dtype=np.float32)

        try:
            # 1. Primary transcription model
            print("Warming up Whisper 'base'...")
            primary = get_model_by_name("base")
            lock = get_inference_lock("base")
            with lock:
                segs, _ = primary.transcribe(silence, language="en", vad_filter=False)
                list(segs)

            # 2. Live-preview model
            print("Warming up Whisper 'tiny.en'...")
            preview = get_model_by_name("tiny.en")
            lock_p = get_inference_lock("tiny.en")
            with lock_p:
                segs, _ = preview.transcribe(silence, language="en", vad_filter=False)
                list(segs)

            # 3. Ollama LLM (optional — silently ignored if not running)
            print("Warming up Ollama LLM...")
            ollama_warmup()

            print("All models ready.")
        except Exception as exc:  # noqa: BLE001
            print(f"Warmup warning: {exc}")
        finally:
            if on_complete:
                on_complete()

    threading.Thread(target=_load, daemon=True).start()
