import json
from pathlib import Path
from datetime import datetime
import sys

# Add config directory to path
CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
if str(CONFIG_DIR) not in sys.path:
    sys.path.insert(0, str(CONFIG_DIR))

from config import HISTORY_PATH

MAX_ENTRIES = 5

def save(raw: str, cleaned: str, app: str, latency_ms: int):
    """Save a transcription entry to history."""
    entries = load()
    entries.insert(0, {
        "timestamp": datetime.now().isoformat(),
        "app": app,
        "raw": raw,
        "cleaned": cleaned,
        "latency_ms": latency_ms
    })
    entries = entries[:MAX_ENTRIES]
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(entries, indent=2))

def load() -> list:
    """Load all history entries."""
    if not HISTORY_PATH.exists():
        return []
    return json.loads(HISTORY_PATH.read_text())

def latest() -> dict | None:
    """Get the most recent history entry."""
    entries = load()
    return entries[0] if entries else None
