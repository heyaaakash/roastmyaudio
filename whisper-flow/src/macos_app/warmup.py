import threading
import numpy as np
import sys
from pathlib import Path

# Fix path to find src.web_ui
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.web_ui.app import get_model_by_name
from llm_cleanup import warmup as ollama_warmup

def load_models_async(on_complete=None):
    """Load both primary and preview models in background thread on launch."""
    def _load():
        try:
            # 1. Warm up the primary model (turbo)
            print("🚀 Warming up Whisper primary model (turbo)...")
            primary_model = get_model_by_name("turbo")
            silence = np.zeros(16000, dtype=np.float32)
            primary_model.transcribe(silence, language="en", verbose=False)
            
            # 2. Warm up the live preview model (tiny.en)
            print("🚀 Warming up Whisper preview model (tiny.en)...")
            preview_model = get_model_by_name("tiny.en")
            preview_model.transcribe(silence, language="en", verbose=False)
            
            # 3. Warm up the Ollama LLM
            print("🚀 Warming up Ollama LLM cleanup...")
            ollama_warmup()
            
            print("✅ All models pre-loaded on GPU and ready.")
            if on_complete:
                on_complete()
        except Exception as e:
            print(f"⚠️  Warmup failed: {e}")
            if on_complete:
                on_complete()
    
    t = threading.Thread(target=_load, daemon=True)
    t.start()
