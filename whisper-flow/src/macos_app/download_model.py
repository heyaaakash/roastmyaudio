#!/usr/bin/env python3
"""
Pre-download and cache a Faster-Whisper model.
Run this once, then latency tests will be fast.

Usage:
    python3 download_model.py -m base
    python3 download_model.py -m large-v3-turbo
"""

import sys
import time
from pathlib import Path
from datetime import datetime

# Fix path to find src.web_ui
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.web_ui.app import get_model_by_name


def log(message: str):
    """Print message with timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def download_and_cache_model(model_name: str):
    """Download and cache a model. This is a one-time operation."""
    log("=" * 70)
    log(f"STEP 1: Downloading and caching '{model_name}' model")
    log("=" * 70)
    
    log(f"Target model: {model_name}")
    log("Note: Large models (1-2GB) may take 5-15 minutes depending on connection")
    log("You will see a progress bar below showing download status...\n")
    
    try:
        log("⏳ Initializing model download...")
        start_time = time.time()
        
        log("⏳ Connecting to Hugging Face Hub and downloading model files...v")
        log("   (Progress bar will appear below)\n")
        
        model = get_model_by_name(model_name)
        
        elapsed = time.time() - start_time
        log(f"\n✓ SUCCESS: Model loaded in {elapsed:.1f}s")
        log(f"✓ {model_name} model is now cached and ready")
        log(f"✓ Future runs will be much faster (no re-download)\n")
        
        log("=" * 70)
        log("NEXT STEP: Run latency tests")
        log("=" * 70)
        log(f"Command:")
        log(f"  python3 test_latency_simple.py -n 20 -m {model_name}\n")
        
        return True
    except KeyboardInterrupt:
        log("\n✗ CANCELLED by user")
        return False
    except Exception as e:
        log(f"\n✗ ERROR during model download: {e}")
        log(f"✗ Please check your internet connection and try again\n")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Pre-download Faster-Whisper model")
    parser.add_argument(
        "-m", "--model",
        type=str,
        default="base",
        help="Model to download (default: base, options: tiny, small, base, medium, large-v3, large-v3-turbo)"
    )
    
    args = parser.parse_args()
    
    success = download_and_cache_model(args.model)
    sys.exit(0 if success else 1)
