import json
from pathlib import Path

DICT_PATH = Path.home() / ".wispr_local" / "dictionary.json"

def load() -> list[str]:
    if not DICT_PATH.exists():
        return []
    return json.loads(DICT_PATH.read_text()).get("words", [])

def add(word: str):
    words = load()
    if word not in words:
        words.append(word)
        DICT_PATH.parent.mkdir(parents=True, exist_ok=True)
        DICT_PATH.write_text(json.dumps({"words": words}, indent=2))

def remove(word: str):
    words = load()
    words = [w for w in words if w != word]
    DICT_PATH.write_text(json.dumps({"words": words}, indent=2))

def as_prompt() -> str:
    """Format words as Whisper initial_prompt."""
    words = load()
    if not words:
        return ""
    return ", ".join(words) + "."
