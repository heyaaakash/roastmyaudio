# ========== LLM LAYER ENABLED ==========
# Advanced hybrid cleaning: LLM (Ollama) + Rule-based formatting
# Uses llama3.2:1b (fast advanced model) for initial cleanup
# Then applies rule-based formatting for structure and polish
# ==========================================

import re
import sys
import time
from pathlib import Path

import requests

# Add config directory to path
CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
if str(CONFIG_DIR) not in sys.path:
    sys.path.insert(0, str(CONFIG_DIR))

from config import OLLAMA_MODEL, OLLAMA_URL  # noqa: E402

CONTEXT_PROMPTS = {
    "default":      "professional and clear",
    "mail":         "formal email tone",
    "outlook":      "formal email tone",
    "slack":        "casual, conversational",
    "messages":     "casual, conversational",
    "notes":        "clear and concise",
    "xcode":        "technical, precise",
    "cursor":       "technical, precise",
    "notion":       "structured and clear",
    "github":       "technical and concise",
    "asana":        "professional task format",
    "jira":         "technical task format",
}

def get_tone(app_name: str) -> str:
    """Determine the appropriate tone based on target application."""
    if not app_name:
        return CONTEXT_PROMPTS["default"]
    key = app_name.lower()
    for k, v in CONTEXT_PROMPTS.items():
        if k in key:
            return v
    return CONTEXT_PROMPTS["default"]

def build_prompt(raw_text: str, app_name: str = None) -> str:
    """Build a prompt for intelligent dictation cleaning."""
    return f"""You are an invisible, direct dictation assistant.

TASK: Clean this voice transcript by:
1. Removing filler words: um, uh, like, so, basically, you know, right, okay, well, actually
2. Fixing grammar and capitalization
3. Resolving self-corrections (e.g., "5pm no actually 6pm" → "6pm")
4. Formatting punctuation correctly

RULES:
- Keep the original meaning and word choices
- Do NOT rewrite or rephrase sentences
- Do NOT change tone or intent
- OUTPUT ONLY the final clean text
- Do NOT include introductory phrases like "Here is" or "The cleaned text is"
- Do NOT use quotes around the output

TRANSCRIPT:
{raw_text}"""

def clean(raw_text: str, app_name: str = None) -> tuple[str, int]:
    """
    Clean raw transcription using advanced Ollama LLM.

    Args:
        raw_text: Raw voice transcript
        app_name: Target application name (determines tone)

    Returns:
        Tuple of (cleaned_text, latency_ms)
    """
    if not raw_text or not raw_text.strip():
        return raw_text, 0

    t0 = time.time()

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": build_prompt(raw_text, app_name),
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": len(raw_text.split()) + 12,  # Tighter output window
        }
    }

    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=20)
        resp.raise_for_status()
        result = resp.json()
        cleaned = result["response"].strip()

        # Remove meta-commentary preambles the model might add
        preamble_patterns = [
            r"^here is the cleaned.*?:\s*",
            r"^here's the cleaned.*?:\s*",
            r"^below is the.*?:\s*",
            r"^cleaned transcript.*?:\s*",
            r"^result.*?:\s*",
            r"^output.*?:\s*",
            r"^cleaned text.*?:\s*",
            r"^cleaned.*?:\s*",
        ]

        for pattern in preamble_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

        # Detect if model rewrote the content
        # Compare word lists (case-insensitive, excluding small words)
        raw_words = set(w.lower() for w in raw_text.split() if len(w) > 3)
        cleaned_words = set(w.lower() for w in cleaned.split() if len(w) > 3)

        # If word lists are too different, model probably rewrote it
        if raw_words and cleaned_words:
            overlap = len(raw_words & cleaned_words) / len(raw_words)
            # If less than 70% of original words remain, it's a rewrite
            if overlap < 0.70:
                print(f"⚠️  Detected content rewrite (only {overlap*100:.0f}% word overlap) — returning raw transcript")
                return raw_text, 0

        # Check if model refused or generated meta-commentary
        refusal_patterns = [
            "i cannot",
            "i cannot fulfill",
            "i cannot help",
            "i cannot process",
            "i cannot generate",
            "i cannot provide",
            "would violate",
            "policy",
            "unfortunately",
            "i appreciate",
            "please note"
        ]

        # If refusal detected, return raw text with no processing
        if any(pattern in cleaned.lower() for pattern in refusal_patterns):
            print("⚠️  Model refused processing — returning raw transcript")
            return raw_text, 0

        latency_ms = int((time.time() - t0) * 1000)
        return cleaned, latency_ms
    except requests.exceptions.ConnectionError:
        print("⚠️  Ollama not running on localhost:11434 — returning raw transcript")
        return raw_text, 0
    except requests.exceptions.Timeout:
        print("⚠️  LLM cleanup timeout — returning raw transcript")
        return raw_text, 0
    except Exception as e:
        print(f"⚠️  LLM cleanup failed: {e}")
        return raw_text, 0


def warmup():
    """
    Warm up the Ollama model by making a dummy call.
    Call this at app startup to load the model into memory,
    avoiding latency hit on the first real transcription.
    """
    clean("test warm up", "default")


if __name__ == "__main__":
    print("Warming up model...")
    clean("test warmup", None)
    print("Ready.\n")

    test_cases = [
        ("um so I wanted to uh meet at 5pm no actually 6pm on thursday", "mail"),
        ("can you like uh add this to the you know the backlog", "slack"),
        ("the function should uh return a list no wait a dictionary", "xcode"),
    ]
    for raw, app in test_cases:
        cleaned, ms = clean(raw, app)
        print(f"App:     {app}")
        print(f"Raw:     {raw}")
        print(f"Cleaned: {cleaned}")
        print(f"LLM ms:  {ms}ms\n")
