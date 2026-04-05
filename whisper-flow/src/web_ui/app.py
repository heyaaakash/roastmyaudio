import os
import re
import sys
import tempfile
import threading
from time import perf_counter
from pathlib import Path
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request
from src.macos_app.dictionary import as_prompt
from src.macos_app.history import save as save_history

app = Flask(__name__)

# Store uploads inside the web_mvp project folder.
TEMP_AUDIO_DIR = Path(__file__).resolve().parent / "temp_uploads"
TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

MODEL_NAME = os.environ.get("WHISPER_MODEL", "turbo")
MODEL_CACHE = {}
MODEL_CACHE_LOCK = threading.Lock()
MODEL_INFERENCE_LOCKS = {}

DEFAULT_CACHE_ROOT = Path(os.path.expanduser("~")) / ".cache"
# OpenAI Whisper uses HuggingFace Hub cache (~/.cache/huggingface) by default
WHISPER_CACHE_DIR = Path(os.getenv("XDG_CACHE_HOME", str(DEFAULT_CACHE_ROOT))) / "huggingface"

# Faster-whisper model names
AVAILABLE_MODELS = [
    "tiny",
    "tiny.en",
    "base",
    "base.en",
    "small",
    "small.en",
    "medium",
    "medium.en",
    "large-v3",
    "large-v3-turbo",
    "turbo",
]

MODEL_ALIAS_TO_CANONICAL = {
    "large-v3": "large-v3",
    "large-v3-turbo": "large-v3-turbo",
}

MODEL_DISPLAY_ORDER = [
    "tiny.en",
    "tiny",
    "base.en",
    "base",
    "small.en",
    "small",
    "medium.en",
    "medium",
    "large-v3",
    "large-v3-turbo",
    "turbo",
]

LIVE_PREVIEW_MODEL_PREFERENCE = ["tiny.en", "tiny", "base.en", "base"]
LIVE_PREVIEW_WORD_LIMIT = 6


ORDINAL_ORDER = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
}

SPOKEN_COMMAND_REPLACEMENTS = [
    (r"\bnew\s+paragraph\b", "\n\n"),
    (r"\b(new\s+line|next\s+line|line\s+break)\b", "\n"),
    (r"\b(bullet\s+point|bullet|dash\s+point)\b", "\n- "),
    (r"\bopen\s+parenthesis\b", "("),
    (r"\bclose\s+parenthesis\b", ")"),
    (r"\bopen\s+bracket\b", "("),
    (r"\bclose\s+bracket\b", ")"),
    (r"\bopen\s+quote\b", '"'),
    (r"\bclose\s+quote\b", '"'),
    (r"\bquote\s+unquote\b", '"'),
    (r"\b(comma)\b", ","),
    (r"\b(period|full\s+stop|dot)\b", "."),
    (r"\b(question\s+mark)\b", "?"),
    (r"\b(exclamation\s+mark|exclamation\s+point)\b", "!"),
    (r"\b(colon)\b", ":"),
    (r"\b(semicolon)\b", ";"),
]

COMPILED_SPOKEN_COMMAND_REPLACEMENTS = [
    (re.compile(pattern, re.IGNORECASE), replacement)
    for pattern, replacement in SPOKEN_COMMAND_REPLACEMENTS
]

STEP_NUMBER_RE = re.compile(
    r"\b(step|point|number|item)\s+(\d+)\b\s*(?:is|:)?\s*",
    re.IGNORECASE,
)

COMMAND_TRIGGER_RE = re.compile(
    r"\b(new\s+paragraph|new\s+line|line\s+break|next\s+line|"
    r"bullet|dash\s+point|comma|period|full\s+stop|dot|question\s+mark|"
    r"exclamation\s+mark|exclamation\s+point|colon|semicolon|open\s+quote|"
    r"close\s+quote|quote\s+unquote|open\s+parenthesis|close\s+parenthesis|"
    r"open\s+bracket|close\s+bracket|step\s+\d+|point\s+\d+|number\s+\d+|item\s+\d+)\b",
    re.IGNORECASE,
)

ORDINAL_PATTERN = re.compile(
    r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)"
    r"(?:\s+one)?\s*(?:is|:)?\s+",
    re.IGNORECASE,
)

FAST_PATH_BYPASS_RE = re.compile(
    r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
    r"step\s+\d+|point\s+\d+|number\s+\d+|item\s+\d+|bullet|new\s+line|"
    r"new\s+paragraph|comma|period|question\s+mark|exclamation\s+mark|"
    r"colon|semicolon|open\s+quote|close\s+quote|open\s+parenthesis|close\s+parenthesis)\b",
    re.IGNORECASE,
)

WHITESPACE_RE = re.compile(r"\s+")
CAP_AFTER_PUNCT_RE = re.compile(r"([.!?]\s+)([a-z])")
PUNCT_SPACING_BEFORE_RE = re.compile(r"\s+([,.;:!?])")
PUNCT_SPACING_AFTER_RE = re.compile(r"([,.;:!?])([A-Za-z])")
PAREN_SPACING_BEFORE_CLOSE_RE = re.compile(r"\s+([\)])")
PAREN_SPACING_AFTER_OPEN_RE = re.compile(r"([\(])\s+")
LINE_SPACING_RE = re.compile(r" *\n *")
BLANK_LINES_RE = re.compile(r"\n{3,}")
LIST_BULLET_PREFIX_RE = re.compile(r"^-\s*")
LIST_NUMBER_PREFIX_RE = re.compile(r"^(\d+)\.\s*")
LINE_PREFIX_RE = re.compile(r"^(\s*(?:-\s+|\d+\.\s+))(.*)$")
QUOTE_LEFT_INNER_SPACE_RE = re.compile(r'"\s+(?=\w)')
QUOTE_RIGHT_INNER_SPACE_RE = re.compile(r'\s+"(?=\s|$|[.,;:!?])')
PAREN_LEFT_INNER_SPACE_RE = re.compile(r"\(\s+")
PAREN_RIGHT_INNER_SPACE_RE = re.compile(r"\s+\)")
NUMBERED_LINE_RE = re.compile(r"^(\d+)[\.)]\s*(.+)$")
TRIM_LIST_BOUNDARY_START_RE = re.compile(r"^[,;:\-\s]+")
TRIM_LIST_BOUNDARY_END_RE = re.compile(r"[,;:\-\s]+$")
TRAILING_CONNECTOR_RE = re.compile(r"\b(and|then)\s*$", re.IGNORECASE)


def _filter_hallucinations(text: str) -> str:
    """
    Filter out hallucinated text patterns that Whisper commonly generates.
    
    Aggressive detection of:
    - Single words/phrases repeated excessively (>10% of transcript)
    - Filler-heavy transcriptions (>30% fillers and pronouns)
    
    Args:
        text: Raw transcription text from Whisper
        
    Returns:
        Filtered text with hallucinations removed
    """
    if not text or len(text.strip()) < 3:
        return text
    
    words = text.split()
    if not words:
        return text
    
    total_words = len(words)
    
    # Count word frequencies
    word_counts = {}
    for word in words:
        normalized = word.lower().rstrip('.,!?;:')
        word_counts[normalized] = word_counts.get(normalized, 0) + 1
    
    # Find the most repeated word
    if word_counts:
        most_common_word = max(word_counts, key=word_counts.get)
        most_common_count = word_counts[most_common_word]
        
        # If any single word is >10% of text, it's likely a hallucination
        if most_common_count / total_words > 0.1:
            # Remove all instances of this dominant hallucination word
            filtered_words = [
                w for w in words
                if w.lower().rstrip('.,!?;:') != most_common_word
            ]
            if filtered_words:
                # Recursively apply filter to catch secondary hallucinations
                return _filter_hallucinations(" ".join(filtered_words))
            return ""
    
    # Filler/pronoun detection
    hallucination_indicators = {
        'you', 'i', 'uh', 'um', 'ah', 'so', 'ok', 'thank', 'well', 'like', 'just'
    }
    
    hallucin_count = sum(
        1 for word in words 
        if word.lower().rstrip('.,!?;:') in hallucination_indicators
    )
    
    # If >30% are fillers, extract only content
    if hallucin_count / total_words > 0.3:
        real_words = [
            w for w in words 
            if w.lower().rstrip('.,!?;:') not in hallucination_indicators
        ]
        if real_words and len(real_words) >= 3:
            return " ".join(real_words)
        return ""
    
    # Strip leading/trailing junk
    start_idx = 0
    for i, word in enumerate(words):
        normalized = word.lower().rstrip('.,!?;:')
        if normalized not in hallucination_indicators and len(normalized) > 1:
            start_idx = i
            break
    
    end_idx = len(words) - 1
    for i in range(len(words) - 1, -1, -1):
        normalized = words[i].lower().rstrip('.,!?;:')
        if normalized not in hallucination_indicators and len(normalized) > 1:
            end_idx = i
            break
    
    if start_idx <= end_idx:
        return " ".join(words[start_idx:end_idx + 1]).strip()
    
    return ""


def get_model():
    return get_model_by_name(MODEL_NAME)


def get_installed_models() -> list[str]:
    # faster-whisper downloads models on demand, so return all available models
    return MODEL_DISPLAY_ORDER


def get_default_model_name() -> str:
    installed = get_installed_models()
    if MODEL_NAME in installed:
        return MODEL_NAME
    return installed[0] if installed else MODEL_NAME


def get_model_by_name(model_name: str):
    requested_name = model_name.strip()
    if requested_name in MODEL_ALIAS_TO_CANONICAL:
        requested_name = MODEL_ALIAS_TO_CANONICAL[requested_name]

    if requested_name not in AVAILABLE_MODELS:
        raise ValueError(f"Unknown model '{model_name}'")

    with MODEL_CACHE_LOCK:
        if requested_name not in MODEL_CACHE:
            # Detect and use Apple Silicon GPU (MPS) for 5-10x speed boost
            import torch
            device = "mps" if torch.backends.mps.is_available() else "cpu"
            print(f"🚀 Loading Whisper model '{requested_name}' on device: {device}")
            
            MODEL_CACHE[requested_name] = whisper.load_model(
                requested_name,
                device=device
            )
        if requested_name not in MODEL_INFERENCE_LOCKS:
            MODEL_INFERENCE_LOCKS[requested_name] = threading.Lock()
    return MODEL_CACHE[requested_name]


def get_model_inference_lock(model_name: str):
    requested_name = model_name.strip()
    if requested_name in MODEL_ALIAS_TO_CANONICAL:
        requested_name = MODEL_ALIAS_TO_CANONICAL[requested_name]

    with MODEL_CACHE_LOCK:
        lock = MODEL_INFERENCE_LOCKS.get(requested_name)
        if lock is None:
            lock = threading.Lock()
            MODEL_INFERENCE_LOCKS[requested_name] = lock
        return lock


def get_preview_model_name(selected_model: str | None = None) -> str:
    installed = get_installed_models()
    if not installed:
        return get_default_model_name()

    for candidate in LIVE_PREVIEW_MODEL_PREFERENCE:
        if candidate in installed:
            return candidate

    preferred = (selected_model or "").strip()
    if preferred in installed:
        return preferred

    return installed[0]


def get_tail_words(text: str, word_limit: int = LIVE_PREVIEW_WORD_LIMIT) -> str:
    words = text.split()
    if not words:
        return ""
    return " ".join(words[-word_limit:])


def _clean_text(text: str) -> str:
    text = WHITESPACE_RE.sub(" ", text).strip()
    if not text:
        return ""

    # Capitalize the first character and punctuation-following sentence starts.
    text = text[0].upper() + text[1:]
    text = CAP_AFTER_PUNCT_RE.sub(lambda m: m.group(1) + m.group(2).upper(), text)
    return text


def _apply_spoken_commands(text: str) -> str:
    if not COMMAND_TRIGGER_RE.search(text):
        return text

    result = text
    for pattern, replacement in COMPILED_SPOKEN_COMMAND_REPLACEMENTS:
        result = pattern.sub(replacement, result)

    # Allow spoken "step 1" / "point 2" to become numbered items.
    result = STEP_NUMBER_RE.sub(r"\n\2. ", result)
    return result


def _normalize_quotes_and_parentheses(text: str) -> str:
    # Clean spacing around paired punctuation without changing semantic content.
    text = QUOTE_LEFT_INNER_SPACE_RE.sub('"', text)
    text = QUOTE_RIGHT_INNER_SPACE_RE.sub('"', text)
    text = PAREN_LEFT_INNER_SPACE_RE.sub("(", text)
    text = PAREN_RIGHT_INNER_SPACE_RE.sub(")", text)
    return text


def _capitalize_line(line: str) -> str:
    if not line:
        return line

    # Preserve list prefixes while capitalizing the content.
    prefix_match = LINE_PREFIX_RE.match(line)
    if prefix_match:
        prefix = prefix_match.group(1)
        content = prefix_match.group(2)
    else:
        prefix = ""
        content = line

    content = content.strip()
    if not content:
        return prefix.rstrip()

    content = content[0].upper() + content[1:]
    content = CAP_AFTER_PUNCT_RE.sub(lambda m: m.group(1) + m.group(2).upper(), content)
    return f"{prefix}{content}".rstrip()


def _normalize_structured_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n")
    normalized = re.sub(r"[\t ]+", " ", normalized)
    normalized = PUNCT_SPACING_BEFORE_RE.sub(r"\1", normalized)
    normalized = PUNCT_SPACING_AFTER_RE.sub(r"\1 \2", normalized)
    normalized = PAREN_SPACING_BEFORE_CLOSE_RE.sub(r"\1", normalized)
    normalized = PAREN_SPACING_AFTER_OPEN_RE.sub(r"\1", normalized)
    normalized = LINE_SPACING_RE.sub("\n", normalized)
    normalized = BLANK_LINES_RE.sub("\n\n", normalized)
    normalized = _normalize_quotes_and_parentheses(normalized)

    lines = [line.strip() for line in normalized.strip().split("\n")]
    formatted_lines = []
    for line in lines:
        if not line:
            formatted_lines.append("")
            continue
        line = LIST_BULLET_PREFIX_RE.sub("- ", line)
        line = LIST_NUMBER_PREFIX_RE.sub(r"\1. ", line)
        formatted_lines.append(_capitalize_line(line))

    normalized = "\n".join(formatted_lines).strip()

    # Ensure readable ending punctuation for plain single-line text.
    if normalized and "\n" not in normalized and normalized[-1] not in ".!?":
        normalized += "."
    return normalized


def _format_ordinal_steps(text: str) -> str:
    matches = list(ORDINAL_PATTERN.finditer(text))
    if len(matches) < 2:
        return text

    items = []
    expected = 1
    for index, match in enumerate(matches):
        ordinal = match.group(1).lower()
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        raw_value = text[match.end() : next_start]
        value = _clean_text(raw_value)
        value = TRIM_LIST_BOUNDARY_START_RE.sub("", value)
        value = TRIM_LIST_BOUNDARY_END_RE.sub("", value)
        value = TRAILING_CONNECTOR_RE.sub("", value).strip()
        value = value.rstrip(".?!")
        if ORDINAL_ORDER.get(ordinal) != expected:
            break
        if not value:
            break
        items.append(value)
        expected += 1

    if len(items) < 2:
        return text

    intro = _clean_text(text[: matches[0].start()]).rstrip(".:")
    intro_line = f"{intro}:" if intro else "Steps:"
    list_block = "\n".join(f"{index}. {item}" for index, item in enumerate(items, start=1))
    return f"{intro_line}\n{list_block}"


def _normalize_numbered_lists(text: str) -> str:
    lines = text.split("\n")
    normalized_lines = []
    expected = 1
    in_numbered_block = False

    for line in lines:
        stripped = line.strip()
        match = NUMBERED_LINE_RE.match(stripped)
        if not match:
            in_numbered_block = False
            expected = 1
            normalized_lines.append(line)
            continue

        number = int(match.group(1))
        content = match.group(2).strip()
        if not in_numbered_block:
            in_numbered_block = True
            expected = 1

        # Re-number contiguous blocks to fix accidental skips/repeats from ASR.
        if number != expected:
            number = expected

        normalized_lines.append(f"{number}. {content}")
        expected += 1

    return "\n".join(normalized_lines)


def format_transcript(text: str) -> str:
    if not text or not text.strip():
        return ""

    stripped = text.strip()

    # Fast path for plain dictation with no spoken formatting commands.
    if not FAST_PATH_BYPASS_RE.search(stripped):
        plain = _clean_text(stripped)
        if plain and plain[-1] not in ".!?":
            plain += "."
        return plain

    commanded = _apply_spoken_commands(stripped)
    commanded = commanded.strip()

    # Prefer automatic step-list formatting when no explicit bullets/line breaks are dictated.
    if "\n" not in commanded and "- " not in commanded:
        ordinal_formatted = _format_ordinal_steps(commanded)
        if "\n" in ordinal_formatted:
            return _normalize_structured_text(_normalize_numbered_lists(ordinal_formatted))

    return _normalize_structured_text(_normalize_numbered_lists(commanded))


def format_transcript_strict(text: str) -> str:
    """Minimal formatting: only normalize whitespace, preserve everything else exactly as said."""
    if not text or not text.strip():
        return ""
    
    # Just clean up excessive whitespace, nothing else
    cleaned = " ".join(text.split())
    return cleaned


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/models")
def models():
    installed = get_installed_models()
    default_model = get_default_model_name()
    return jsonify({"models": installed, "default_model": default_model})


@app.post("/transcribe")
def transcribe():
    audio_file = request.files.get("audio")
    if audio_file is None:
        return jsonify({"error": "No audio file provided."}), 400

    suffix = Path(audio_file.filename or "recording.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(
        dir=TEMP_AUDIO_DIR,
        suffix=suffix,
        delete=False,
    ) as temp_file:
        audio_path = Path(temp_file.name)
        audio_file.save(temp_file)

    try:
        selected_model = (request.form.get("model") or "").strip() or get_default_model_name()
        strict_mode = (request.form.get("strict_mode") or "").lower() == "true"
        model = get_model_by_name(selected_model)
        with get_model_inference_lock(selected_model):
            # Whisper returns a dict: {"segments": [...], "language": str}
            result = model.transcribe(
                str(audio_path),
                language="en",
                verbose=False,
                no_speech_threshold=0.8,
                logprob_threshold=-1.0,
                compression_ratio_threshold=2.4,
                condition_on_previous_text=False,
            )
            # Filter by BOTH no_speech_prob and avg_logprob
            segments = [
                seg for seg in result["segments"] 
                if seg.get("no_speech_prob", 0) < 0.2 
                and seg.get("avg_logprob", -1.0) > -0.5
            ]
            raw_text = " ".join(seg["text"].strip() for seg in segments)
            
            # 🛑 BREAK HALLUCINATION LOOPS (Repetitive phrase detection)
            import re
            cleaned_raw = re.sub(r'[^\w\s]', '', raw_text.lower()).strip()
            words = cleaned_raw.split()

            # Silence fallback blacklist 
            hallucination_blacklist = ["thank you", "thanks for watching", "subtitle", "please subscribe", "the end"]
            if cleaned_raw in hallucination_blacklist:
                print(f"🛑 Blocking blacklisted silence hallucination: '{raw_text}'")
                return jsonify({"raw_text": "", "cleaned_text": "", "status": "no_speech"})

            if len(words) >= 4:
                phrase_counts = {}
                for i in range(len(words)-1):
                    p = f"{words[i]} {words[i+1]}"
                    phrase_counts[p] = phrase_counts.get(p, 0) + 1
                if any(count > 2 for count in phrase_counts.values()):
                    print(f"⚠️  Discarding repetitive hallucination loop: {raw_text[:50]}...")
                    return jsonify({"raw_text": "", "cleaned_text": "", "status": "no_speech"})
            
            # Filter out hallucinated repeated/nonsensical phrases
            raw_text = _filter_hallucinations(raw_text)
        formatter_start = perf_counter()
        formatted_text = format_transcript_strict(raw_text) if strict_mode else format_transcript(raw_text)
        formatter_ms = round((perf_counter() - formatter_start) * 1000, 3)
        
        # Save to history
        app_name = (request.form.get("app") or "").strip() or "unknown"
        save_history(raw_text, formatted_text, app_name, formatter_ms)
        
        return jsonify(
            {
                "text": formatted_text,
                "raw_text": raw_text,
                "saved_path": str(audio_path),
                "formatter_ms": formatter_ms,
                "model_used": selected_model,
                "transcribed_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Transcription failed: {exc}"}), 500


@app.post("/transcribe_partial")
def transcribe_partial():
    audio_file = request.files.get("audio")
    if audio_file is None:
        return jsonify({"error": "No audio file provided."}), 400

    suffix = Path(audio_file.filename or "preview.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(
        dir=TEMP_AUDIO_DIR,
        suffix=suffix,
        delete=False,
    ) as temp_file:
        audio_path = Path(temp_file.name)
        audio_file.save(temp_file)

    try:
        selected_model = (request.form.get("model") or "").strip() or get_default_model_name()
        preview_model = get_preview_model_name(selected_model)
        model = get_model_by_name(preview_model)
        with get_model_inference_lock(preview_model):
            # Whisper live-preview transcription
            result = model.transcribe(
                str(audio_path),
                language="en",
                verbose=False,
            )
            raw_text = " ".join(seg["text"].strip() for seg in result["segments"])
            # Filter out hallucinated repeated/nonsensical phrases
            raw_text = _filter_hallucinations(raw_text)
        preview_text = get_tail_words(raw_text)

        return jsonify(
            {
                "preview_text": preview_text,
                "raw_text": raw_text,
                "model_used": preview_model,
                "transcribed_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Live preview failed: {exc}"}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
