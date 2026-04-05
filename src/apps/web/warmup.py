import threading
import numpy as np
import sys
from pathlib import Path

# Add source directory to path
SRC_DIR = Path(__file__).resolve().parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Import from shared modules
from shared.llm_cleanup import warmup as ollama_warmup

def load_models_async(on_complete=None):
    """
    Load both primary and preview models in background thread on launch.
    
    Args:
        on_complete: Callback function to call when loading is complete
    """
    def _load():
        try:
            # Import here to avoid circular imports
            from apps.web.app import get_model_by_name
            
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
