"""
Background model warmup for the Flask web app.

Pre-loads Whisper models and warms up Ollama at startup.
"""

import sys
import threading
from pathlib import Path
from typing import Callable, Optional

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[3]
for _p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "config")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from src.shared.llm_cleanup import warmup as ollama_warmup  # noqa: E402
from src.shared.transcriber import get_inference_lock, get_model_by_name  # noqa: E402


def load_models_async(on_complete: Optional[Callable] = None) -> None:
    """Pre-load base + tiny.en models and warm up Ollama in a daemon thread."""

    def _load():
        silence = np.zeros(16_000, dtype=np.float32)
        try:
            print("Warming up Whisper 'base'...")
            m = get_model_by_name("base")
            with get_inference_lock("base"):
                segs, _ = m.transcribe(silence, language="en", vad_filter=False)
                list(segs)

            print("Warming up Whisper 'tiny.en'...")
            mp = get_model_by_name("tiny.en")
            with get_inference_lock("tiny.en"):
                segs, _ = mp.transcribe(silence, language="en", vad_filter=False)
                list(segs)

            print("Warming up Ollama LLM...")
            ollama_warmup()

            print("Web UI models ready.")
        except Exception as exc:  # noqa: BLE001
            print(f"Warmup warning: {exc}")
        finally:
            if on_complete:
                on_complete()

    threading.Thread(target=_load, daemon=True).start()
