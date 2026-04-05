import argparse
import os
import sys
from pathlib import Path

def download_faster_whisper_model(model_name: str, cache_dir: str = None):
    """ Download Faster-Whisper model using the library. """
    try:
        from faster_whisper import WhisperModel
        print(f"📦 Downloading Faster-Whisper model: {model_name}...")
        # This will trigger a download if not cached
        WhisperModel(model_name, device="cpu", compute_type="int8", download_root=cache_dir)
        print(f"✅ Faster-Whisper model {model_name} ready.")
    except ImportError:
        print("❌ Error: faster-whisper not installed. Run 'pip install faster-whisper' first.")
    except Exception as e:
        print(f"❌ Error downloading Faster-Whisper model: {e}")

def main():
    parser = argparse.ArgumentParser(description="Whisper Flow - Model Downloader")
    parser.add_argument("--model", type=str, default="turbo", help="Model name (tiny, base, turbo, etc.)")
    parser.add_argument("--cache-dir", type=str, help="Directory to store models")
    
    args = parser.parse_args()
    
    # Simple check for fast-whisper
    download_faster_whisper_model(args.model, args.cache_dir)

if __name__ == "__main__":
    main()
