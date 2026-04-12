import json
import sys
from pathlib import Path

# Add config directory to path
CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
if str(CONFIG_DIR) not in sys.path:
    sys.path.insert(0, str(CONFIG_DIR))

from config import DICTIONARY_PATH  # noqa: E402


def load() -> list[str]:
    """Load custom dictionary words."""
    if not DICTIONARY_PATH.exists():
        return []
    return json.loads(DICTIONARY_PATH.read_text()).get("words", [])

def add(word: str):
    """Add a word to the custom dictionary."""
    words = load()
    if word not in words:
        words.append(word)
        DICTIONARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        DICTIONARY_PATH.write_text(json.dumps({"words": words}, indent=2))

def remove(word: str):
    """Remove a word from the custom dictionary."""
    words = load()
    words = [w for w in words if w != word]
    DICTIONARY_PATH.write_text(json.dumps({"words": words}, indent=2))

def as_prompt() -> str:
    """Format words as Whisper initial_prompt."""
    words = load()
    if not words:
        return ""
    return ", ".join(words) + "."
