"""
Background model warmup for the macOS menu bar app.

Preloads the selected speech/preview models and optional embedded cleanup engine.
Downloads and initialization run off the UI thread; failures remain retryable.
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

from src.shared.llm_cleanup import warmup as llm_warmup  # noqa: E402
from src.shared.settings import load as load_settings  # noqa: E402
from src.shared.transcriber import (  # noqa: E402
    get_inference_lock,
    get_model_by_name,
    get_preview_model_name,
)


def load_models_async(on_complete: Optional[Callable] = None) -> None:
    """Warm the selected models; callback receives whether speech initialization succeeded."""

    def _load():
        settings = load_settings()
        silence = np.zeros(16_000, dtype=np.float32)
        ready = False
        try:
            selected = settings["model"]
            for name in dict.fromkeys((selected, get_preview_model_name(selected))):
                model = get_model_by_name(name)
                with get_inference_lock(name):
                    segments, _ = model.transcribe(silence, language="en", vad_filter=False)
                    list(segments)
            ready = True
            if settings["llm_enabled"]:
                llm_warmup(model_key=settings["llm_model"])
        except Exception as exc:
            print(f"Model warmup unavailable: {type(exc).__name__}")
        finally:
            if on_complete:
                on_complete(ready)

    threading.Thread(target=_load, daemon=True).start()
