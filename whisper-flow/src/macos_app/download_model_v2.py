#!/usr/bin/env python3
"""
Download Faster-Whisper model with real-time progress feedback.
"""

import sys
from pathlib import Path
from datetime import datetime
import os

# Fix path to find src.web_ui
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Fix path for local imports (ditto same)
APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from src.web_ui.app import get_model_by_name


def log(message: str):
    """Print message with timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def get_cache_size(model_name: str) -> str:
    """Check cache directory size."""
    try:
        cache_dir = Path.home() / ".cache" / "faster-whisper"
        if cache_dir.exists():
            total_size = sum(f.stat().st_size for f in cache_dir.rglob('*') if f.is_file())
            return f"{total_size / (1024**3):.2f} GB"
    except:
        pass
    return "unknown"


def download_model_with_progress(model_name: str):
    """Download model with real-time feedback."""
    log("=" * 70)
    log(f"DOWNLOADING: {model_name} model")
    log("=" * 70)
    log("")
    
    log(f"Model: {model_name}")
    log(f"Cache dir: ~/.cache/faster-whisper/")
    log("")
    
    if model_name == "large-v3-turbo":
        log("⏳ Downloading large-v3-turbo (~1.5 GB)")
        log("   Expected time: 5-15 minutes (depends on internet)")
    elif model_name == "base":
        log("⏳ Downloading base model (~140 MB)")
        log("   Expected time: 1-3 minutes")
    elif model_name == "small":
        log("⏳ Downloading small model (~480 MB)")
        log("   Expected time: 2-5 minutes")
    else:
        log(f"⏳ Downloading {model_name} model")
    
    log("   This may take a while... Please wait\n")
    
    # Disable buffering for real-time output
    os.environ['PYTHONUNBUFFERED'] = '1'
    
    try:
        import time
        start_time = time.time()
        start_cache = get_cache_size(model_name)
        
        log("Connecting to Hugging Face Hub...")
        log("(Model download will proceed in background)\n")
        
        model = get_model_by_name(model_name)
        
        elapsed = time.time() - start_time
        end_cache = get_cache_size(model_name)
        
        log(f"\n{'=' * 70}")
        log(f"✓ SUCCESS!")
        log(f"{'=' * 70}")
        log(f"Model: {model_name}")
        log(f"Downloaded in: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
        log(f"Cache size: {end_cache}")
        log("")
        log("Next step: Run latency tests")
        log(f"Command: python3 test_latency_simple.py -n 20 -m {model_name}")
        log(f"{'=' * 70}\n")
        
        return True
        
    except KeyboardInterrupt:
        log("\n✗ Download cancelled by user")
        return False
    except Exception as e:
        log(f"\n{'=' * 70}")
        log(f"✗ ERROR: {type(e).__name__}")
        log(f"{'=' * 70}")
        log(f"Message: {str(e)}")
        log("")
        log("Possible solutions:")
        log("1. Check internet connection")
        log("2. Try again in a few moments")
        log("3. Try with a smaller model (tiny, base, small)")
        log(f"{'=' * 70}\n")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Download Faster-Whisper model")
    parser.add_argument(
        "-m", "--model",
        type=str,
        default="base",
        help="Model: tiny, small, base, medium, large-v3, large-v3-turbo"
    )
    
    args = parser.parse_args()
    
    success = download_model_with_progress(args.model)
    sys.exit(0 if success else 1)
