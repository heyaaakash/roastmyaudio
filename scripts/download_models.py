#!/usr/bin/env python3
"""
Download and cache Whisper models locally.
Models are stored in cache/models/ within the project.

Usage:
    python3 scripts/download_models.py -m turbo tiny.en
    python3 scripts/download_models.py -m all
    python3 scripts/download_models.py -m base --device cpu
"""

import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

# Add config to path
CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
if str(CONFIG_DIR) not in sys.path:
    sys.path.insert(0, str(CONFIG_DIR))

from config import MODELS_CACHE_DIR, PROJECT_ROOT

import whisper


def log(message: str):
    """Print message with timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def get_model_size(model_name: str) -> str:
    """Return estimated size for model."""
    sizes = {
        "tiny": "40MB",
        "tiny.en": "40MB",
        "base": "140MB",
        "base.en": "140MB",
        "small": "480MB",
        "small.en": "480MB",
        "medium": "1.5GB",
        "medium.en": "1.5GB",
        "large-v3": "3GB",
        "large-v3-turbo": "1.6GB",
        "turbo": "1.5GB",
    }
    return sizes.get(model_name, "unknown size")


def download_and_cache_model(model_name: str, device: str = "auto"):
    """Download and cache a model. This is a one-time operation."""
    
    model_name = model_name.strip().lower()
    
    # Validate model name
    available = whisper.available_models()
    if model_name not in available:
        log(f"❌ Unknown model: {model_name}")
        log(f"   Available models: {', '.join(available)}")
        return False
    
    log(f"📥 Downloading model: {model_name} ({get_model_size(model_name)})")
    log(f"   Destination: {MODELS_CACHE_DIR}")
    
    try:
        start_time = time.time()
        
        # Whisper will automatically cache to HF_HOME (set in config.py)
        model = whisper.load_model(model_name, device=device)
        
        elapsed_sec = time.time() - start_time
        
        log(f"✅ Downloaded and cached in {elapsed_sec:.1f}s")
        log(f"   Model: {model_name}")
        log(f"   Size: {get_model_size(model_name)}")
        
        # Verify file exists
        model_files = list(MODELS_CACHE_DIR.glob(f"*{model_name}*"))
        if model_files:
            total_size_mb = sum(f.stat().st_size for f in model_files) / (1024 * 1024)
            log(f"   Verified: {total_size_mb:.0f}MB on disk")
        
        return True
        
    except Exception as e:
        log(f"❌ Failed to download {model_name}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Download Whisper models for local use"
    )
    parser.add_argument(
        "-m", "--models",
        nargs="+",
        required=True,
        help="Model(s) to download. Use 'all' for all models, or specify names like: turbo tiny.en base"
    )
    parser.add_argument(
        "-d", "--device",
        default="auto",
        help="Device to use: 'auto' (default), 'cpu', or 'cuda'"
    )
    
    args = parser.parse_args()
    
    log("🎙️  Whisper Model Downloader")
    log("================================")
    log(f"Cache directory: {MODELS_CACHE_DIR}")
    log("")
    
    # Determine models to download
    if args.models[0].lower() == "all":
        models_to_download = whisper.available_models()
        log(f"Downloading all {len(models_to_download)} available models")
    else:
        models_to_download = [m.lower() for m in args.models]
        log(f"Downloading {len(models_to_download)} model(s): {', '.join(models_to_download)}")
    
    log("")
    log(f"Device: {args.device}")
    log("")
    
    # Download each model
    successful = 0
    failed = 0
    
    for i, model_name in enumerate(models_to_download, 1):
        log(f"[{i}/{len(models_to_download)}]")
        if download_and_cache_model(model_name, args.device):
            successful += 1
        else:
            failed += 1
        log("")
    
    # Summary
    log("================================")
    log(f"Download Summary:")
    log(f"  ✅ Successful: {successful}")
    if failed > 0:
        log(f"  ❌ Failed: {failed}")
    
    total_size_mb = sum(f.stat().st_size for f in MODELS_CACHE_DIR.rglob("*")) / (1024 * 1024)
    log(f"  📊 Total cached: {total_size_mb:.0f}MB")
    log("")
    
    if failed == 0:
        log("🎉 All models downloaded successfully!")
        log(f"Next: python3 src/apps/web/app.py")
        return 0
    else:
        log("⚠️  Some models failed. Check errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
