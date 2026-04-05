import json
from pathlib import Path
from datetime import datetime

HISTORY_PATH = Path.home() / ".wispr_local" / "history.json"
MAX_ENTRIES = 5

def save(raw: str, cleaned: str, app: str, latency_ms: int):
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
    if not HISTORY_PATH.exists():
        return []
    return json.loads(HISTORY_PATH.read_text())

def latest() -> dict | None:
    entries = load()
    return entries[0] if entries else None
