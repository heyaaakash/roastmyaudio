#!/usr/bin/env python3
"""
Download and cache Whisper models locally using faster-whisper.

Models are stored in cache/models/ within the project (HuggingFace cache
layout). This script matches the engine used by the app — faster-whisper
with int8 CPU quantization — so downloaded models load without re-download.

Usage:
    python3 scripts/download_models.py             # interactive picker
    python3 scripts/download_models.py -m base tiny.en
    python3 scripts/download_models.py -m all
    python3 scripts/download_models.py -m base --device cpu
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

# Add config to path
CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
if str(CONFIG_DIR) not in sys.path:
    sys.path.insert(0, str(CONFIG_DIR))

from faster_whisper import WhisperModel  # noqa: E402

from config import MODELS_CACHE_DIR  # noqa: E402

# Models supported by faster-whisper (same names as openai-whisper).
AVAILABLE_MODELS = [
    "tiny", "tiny.en",
    "base", "base.en",
    "small", "small.en",
    "medium", "medium.en",
    "large-v3", "large-v3-turbo",
    "turbo",
]


DEFAULT_MODEL = "base"
# Models recommended for most users (small footprint, good accuracy).
RECOMMENDED_MODELS = ["tiny.en", "base"]


def log(message: str):
    """Print message with timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def _is_model_cached(model_name: str) -> bool:
    """
    Best-effort check for whether a faster-whisper model is already on disk.

    faster-whisper stores each model under a HF-style directory keyed by a
    hashed repo id (e.g. models--Systran--faster-whisper-base). We glob for
    the model name suffix to detect an existing download.
    """
    try:
        pattern = f"*{model_name.replace('.', '-')}*"
        hits = [p for p in MODELS_CACHE_DIR.rglob(pattern) if p.is_dir()]
        if hits:
            return True
        # Also check for the snapshots/ directory layout that HF uses.
        return any(
            p.is_dir() and model_name.replace(".", "-") in p.name.lower()
            for p in MODELS_CACHE_DIR.rglob("models--*")
        )
    except Exception:
        return False


def _prompt_models() -> list[str]:
    """Interactive model picker (used when -m is omitted)."""
    print()
    print("Available models (cached models are marked with ✓):")
    print("-" * 56)
    for i, name in enumerate(AVAILABLE_MODELS, 1):
        cached = "  ✓" if _is_model_cached(name) else ""
        rec = "  (recommended)" if name in RECOMMENDED_MODELS else ""
        print(f"  {i:>2}. {name:<16} {get_model_size(name):<8}{cached}{rec}")
    print("-" * 56)
    print("Enter one or more numbers/names separated by spaces, or:")
    print("  a   = download ALL models")
    print(f"  r   = download RECOMMENDED ({', '.join(RECOMMENDED_MODELS)})")
    print("Enter to skip and exit.")
    print()

    while True:
        try:
            raw = input("Select models> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return []

        if not raw:
            return []

        raw_l = raw.lower()
        if raw_l == "a":
            return list(AVAILABLE_MODELS)
        if raw_l == "r":
            return list(RECOMMENDED_MODELS)

        tokens = raw.replace(",", " ").split()
        chosen: list[str] = []
        valid = True
        for tok in tokens:
            if tok.isdigit():
                idx = int(tok)
                if 1 <= idx <= len(AVAILABLE_MODELS):
                    chosen.append(AVAILABLE_MODELS[idx - 1])
                    continue
                print(f"  ❌ Number {idx} out of range")
                valid = False
                break
            tok_l = tok.lower()
            if tok_l in AVAILABLE_MODELS:
                chosen.append(tok_l)
                continue
            print(f"  ❌ Unknown model: {tok}")
            valid = False
            break
        if not valid:
            print("Please try again.")
            continue
        if not chosen:
            return []
        return chosen


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


def _resolve_device(device: str) -> str:
    """faster-whisper (ctranslate2) has no CUDA on macOS — force cpu."""
    if device in ("auto", "cuda", "gpu"):
        log("   Note: faster-whisper uses CPU (int8) on macOS — ignoring "
            f"--device {device!r}")
    return "cpu"


def download_and_cache_model(model_name: str, device: str = "auto"):
    """Download and cache a model. This is a one-time operation."""

    model_name = model_name.strip().lower()

    # Validate model name
    if model_name not in AVAILABLE_MODELS:
        log(f"❌ Unknown model: {model_name}")
        log(f"   Available models: {', '.join(AVAILABLE_MODELS)}")
        return False

    log(f"📥 Downloading model: {model_name} ({get_model_size(model_name)})")
    log(f"   Destination: {MODELS_CACHE_DIR}")

    try:
        start_time = time.time()

        # faster-whisper downloads from HuggingFace into download_root on
        # first construction. Use the same settings as the transcriber so the
        # cached files are a perfect match (no re-download at runtime).
        WhisperModel(
            model_name,
            device=_resolve_device(device),
            compute_type="int8",
            download_root=str(MODELS_CACHE_DIR),
        )

        elapsed_sec = time.time() - start_time

        log(f"✅ Downloaded and cached in {elapsed_sec:.1f}s")
        log(f"   Model: {model_name}")
        log(f"   Size: {get_model_size(model_name)}")

        # Verify files exist on disk
        model_files = [f for f in MODELS_CACHE_DIR.rglob("*") if f.is_file()]
        if model_files:
            total_size_mb = sum(f.stat().st_size for f in model_files) / (1024 * 1024)
            log(f"   Verified: {total_size_mb:.0f}MB on disk")

        return True

    except Exception as e:
        log(f"❌ Failed to download {model_name}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Download Whisper models for local use (faster-whisper)"
    )
    parser.add_argument(
        "-m", "--models",
        nargs="+",
        default=None,
        help="Model(s) to download. Use 'all' for all models, or specify "
             "names like: turbo tiny.en base. If omitted, launches an "
             "interactive picker.",
    )
    parser.add_argument(
        "-d", "--device",
        default="auto",
        help="Device to use: 'auto' (default), 'cpu', or 'cuda' "
             "(note: macOS forces CPU)",
    )

    args = parser.parse_args()

    log("🎙️  Whisper Model Downloader (faster-whisper)")
    log("================================")
    log(f"Cache directory: {MODELS_CACHE_DIR}")
    log("")

    # Determine models to download
    if args.models is None:
        models_to_download = _prompt_models()
        if not models_to_download:
            log("No models selected. Exiting.")
            return 0
    elif args.models[0].lower() == "all":
        models_to_download = list(AVAILABLE_MODELS)
        log(f"Downloading all {len(models_to_download)} available models")
    else:
        models_to_download = [m.lower() for m in args.models]
        log(f"Downloading {len(models_to_download)} model(s): "
            f"{', '.join(models_to_download)}")

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
    log("Download Summary:")
    log(f"  ✅ Successful: {successful}")
    if failed > 0:
        log(f"  ❌ Failed: {failed}")

    try:
        total_size_mb = sum(
            f.stat().st_size for f in MODELS_CACHE_DIR.rglob("*") if f.is_file()
        ) / (1024 * 1024)
        log(f"  📊 Total cached: {total_size_mb:.0f}MB")
    except Exception:
        pass
    log("")

    if failed == 0:
        log("🎉 All models downloaded successfully!")
        log("Next: make run  (or: python3 src/apps/web/app.py)")
        return 0
    else:
        log("⚠️  Some models failed. Check errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
