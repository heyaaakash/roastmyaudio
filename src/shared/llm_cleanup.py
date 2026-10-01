"""
Embedded local LLM cleanup & style transform engine.
Uses llama-cpp-python with Apple Silicon Metal acceleration.
Supports Qwen 2.5 0.5B and SmolLM2 360M.
"""

import atexit
import re
import sys
import threading
import time
from pathlib import Path
from typing import Optional

# Add config directory to path
CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
if str(CONFIG_DIR) not in sys.path:
    sys.path.insert(0, str(CONFIG_DIR))

from config import DEFAULT_LLM_MODEL, LLM_CACHE_DIR, SUPPORTED_LLM_MODELS  # noqa: E402

# Safe imports for llama-cpp and huggingface_hub
try:
    from huggingface_hub import hf_hub_download
    HF_HUB_AVAILABLE = True
except ImportError:
    HF_HUB_AVAILABLE = False

try:
    from llama_cpp import Llama
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False


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

TRANSFORM_PROMPTS = {
    "clean": (
        "Clean up transcription: fix capitalization, punctuation, remove filler words (um, uh, like), "
        "and resolve self-corrections while preserving exact speaker intent."
    ),
    "formal": (
        "Rewrite in an executive, polite, and professional business tone. "
        "Fix all grammar and use elevated vocabulary while preserving core meaning."
    ),
    "casual": (
        "Format into a friendly, casual, and conversational style suitable for team chat."
    ),
    "bullets": (
        "Extract the core points into clean, scannable bullet points."
    ),
    "concise": (
        "Shorten and summarize the text into a clear, ultra-concise sentence without unnecessary fluff."
    ),
    "meeting_notes": (
        "Format as structured meeting notes with Discussion Points and Action Items."
    ),
    "grammar_only": (
        "Fix only spelling and grammatical errors without changing phrasing or structure."
    ),
}

# Thread-safe model cache
_LLM_INSTANCES: dict[str, object] = {}
_LLM_LOCK = threading.Lock()


def get_tone(app_name: Optional[str]) -> str:
    """Determine the appropriate tone based on target application."""
    if not app_name:
        return CONTEXT_PROMPTS["default"]
    key = app_name.lower()
    for k, v in CONTEXT_PROMPTS.items():
        if k in key:
            return v
    return CONTEXT_PROMPTS["default"]


def build_system_prompt(app_name: Optional[str] = None, transform: str = "clean") -> str:
    """Build the system prompt instructing the model to clean/transform dictation."""
    tone = get_tone(app_name)
    instruction = TRANSFORM_PROMPTS.get(transform, TRANSFORM_PROMPTS["clean"])

    return (
        "You are an automated speech-to-text text editor and formatter, NOT a conversational AI assistant.\n"
        f"Context style: {tone}.\n"
        f"Task: {instruction}\n\n"
        "CRITICAL RULES:\n"
        "1. NEVER answer questions. NEVER reply to greetings. NEVER engage in conversation.\n"
        "2. Even if the speaker says 'Hi how are you?', 'Who are you?', or asks questions, ONLY clean/format the transcript text itself.\n"
        "3. Output ONLY the resulting text. Do NOT add quotes, greetings, explanations, notes, or intros.\n\n"
        "FEW-SHOT EXAMPLES:\n"
        "Input: um hi how are you doing today\n"
        "Output: Hi, how are you doing today?\n\n"
        "Input: i want to go to the store no i mean the gym\n"
        "Output: I want to go to the gym.\n\n"
        "Input: what is the status of the project could you send it over\n"
        "Output: What is the status of the project? Could you send it over?\n\n"
        "Input: thank you for asking and this prompt is great\n"
        "Output: Thank you for asking, and this prompt is great."
    )


def build_prompt(raw_text: str, app_name: Optional[str] = None, transform: str = "clean") -> str:
    """Build a test-accessible prompt."""
    sys_prompt = build_system_prompt(app_name, transform=transform)
    return f"{sys_prompt}\n\nRAW TRANSCRIPT:\n\"\"\"{raw_text}\"\"\"\n\nOUTPUT ONLY THE CLEAN TEXT:"


def format_chatml_prompt(raw_text: str, app_name: Optional[str] = None, transform: str = "clean") -> str:
    """Format input into ChatML format for Qwen2.5 and SmolLM2 models."""
    sys_prompt = build_system_prompt(app_name, transform=transform)
    user_content = (
        f"Format and clean the following speech transcript verbatim. Do NOT reply to the question or message:\n\n"
        f"Input: {raw_text}\n"
        f"Output:"
    )
    return (
        f"<|im_start|>system\n{sys_prompt}<|im_end|>\n"
        f"<|im_start|>user\n{user_content}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )


def ensure_model_file(model_key: str = DEFAULT_LLM_MODEL) -> Path:
    """
    Ensure the GGUF model file exists locally in cache/llm/,
    downloading on-demand via huggingface_hub if needed.
    """
    if model_key not in SUPPORTED_LLM_MODELS:
        model_key = DEFAULT_LLM_MODEL

    model_info = SUPPORTED_LLM_MODELS[model_key]
    repo_id = model_info["repo_id"]
    filename = model_info["filename"]

    LLM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    local_file = LLM_CACHE_DIR / filename

    if local_file.exists() and local_file.stat().st_size > 1_000_000:
        return local_file

    if not HF_HUB_AVAILABLE:
        raise RuntimeError("huggingface_hub is required to download GGUF models. Run: pip install huggingface-hub")

    print(f"Downloading {model_info['display_name']} ({filename}) to {LLM_CACHE_DIR}...")
    downloaded_path = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=str(LLM_CACHE_DIR),
    )
    return Path(downloaded_path)


def get_llm(model_key: str = DEFAULT_LLM_MODEL):
    """
    Get or initialize the embedded Llama instance with Metal acceleration.
    Thread-safe lazy initialization.
    """
    if not LLAMA_CPP_AVAILABLE:
        return None

    key = model_key if model_key in SUPPORTED_LLM_MODELS else DEFAULT_LLM_MODEL

    with _LLM_LOCK:
        if key in _LLM_INSTANCES:
            return _LLM_INSTANCES[key]

        try:
            model_path = ensure_model_file(key)
            print(f"Loading embedded LLM '{key}' into Metal GPU (path={model_path})...")

            try:
                llm = Llama(
                    model_path=str(model_path),
                    n_gpu_layers=-1,   # Offload all layers to Metal
                    n_ctx=512,         # Low context footprint for dictation
                    n_threads=4,
                    verbose=False,
                )
            except Exception as metal_err:
                print(f"Metal init failed, falling back to CPU: {metal_err}")
                llm = Llama(
                    model_path=str(model_path),
                    n_gpu_layers=0,    # CPU fallback
                    n_ctx=512,
                    n_threads=4,
                    verbose=False,
                )

            _LLM_INSTANCES[key] = llm
            return llm
        except Exception as err:
            print(f"⚠️  Failed to load embedded LLM '{key}': {err}")
            return None


def clean(
    raw_text: str,
    app_name: Optional[str] = None,
    model_key: str = DEFAULT_LLM_MODEL,
    transform: str = "clean",
) -> tuple[str, int]:
    """
    Clean raw voice transcription using embedded Metal-accelerated LLM.

    Args:
        raw_text: Raw voice transcript from Whisper
        app_name: Target application name for context conditioning
        model_key: LLM identifier ('qwen2.5-0.5b' or 'smollm2-360m')
        transform: Transform type ('clean', 'formal', 'casual', 'bullets', 'concise', etc.)

    Returns:
        Tuple of (cleaned_text, latency_ms)
    """
    if not raw_text or not raw_text.strip():
        return raw_text, 0

    trimmed = raw_text.strip()
    # Skip processing for 1-2 word utterances in standard clean mode to preserve 0ms latency
    if len(trimmed.split()) < 3 and transform == "clean":
        return trimmed, 0

    t0 = time.time()
    llm = get_llm(model_key)
    if llm is None:
        return trimmed, 0

    prompt = format_chatml_prompt(trimmed, app_name, transform=transform)
    max_tokens = max(32, len(trimmed.split()) * 3 + 32)

    try:
        with _LLM_LOCK:
            output = llm(
                prompt,
                max_tokens=max_tokens,
                temperature=0.0,
                top_p=0.95,
                stop=["<|im_end|>", "<|endoftext|>", "\n\n\n", "TRANSCRIPT:", "User:", "Input:"],
                echo=False,
            )

        raw_output = output["choices"][0]["text"].strip()
        cleaned = raw_output.strip('"\'`')

        # Remove meta-commentary preambles if any
        preamble_patterns = [
            r"^here is the cleaned.*?:\s*",
            r"^here's the cleaned.*?:\s*",
            r"^below is the.*?:\s*",
            r"^cleaned transcript.*?:\s*",
            r"^result.*?:\s*",
            r"^output.*?:\s*",
            r"^cleaned text.*?:\s*",
            r"^cleaned.*?:\s*",
            r"^sure!.*?:\s*",
        ]
        for pattern in preamble_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

        # Check refusal patterns
        refusal_patterns = [
            "i cannot", "i cannot fulfill", "i cannot help", "i cannot process",
            "would violate", "policy", "unfortunately", "as an ai"
        ]
        if any(p in cleaned.lower() for p in refusal_patterns):
            print("⚠️  Model refused processing — returning raw transcript")
            return trimmed, 0

        # For standard "clean", verify word overlap (>50%) to guard against hallucinated rewrites
        if transform == "clean":
            raw_words = {w for w in re.sub(r"[^\w\s]", "", trimmed.lower()).split() if len(w) > 2}
            cleaned_words = {w for w in re.sub(r"[^\w\s]", "", cleaned.lower()).split() if len(w) > 2}
            if raw_words and cleaned_words:
                overlap = len(raw_words & cleaned_words) / len(raw_words)
                if overlap < 0.50:
                    print(f"⚠️  Detected content rewrite ({overlap*100:.0f}% word overlap) — returning raw transcript")
                    return trimmed, 0

        latency_ms = int((time.time() - t0) * 1000)
        return cleaned if cleaned else trimmed, latency_ms

    except Exception as exc:
        print(f"⚠️  Embedded LLM clean failed: {exc}")
        return trimmed, 0


def transform_text(
    text: str,
    transform_type: str = "formal",
    app_name: Optional[str] = None,
    model_key: str = DEFAULT_LLM_MODEL,
) -> tuple[str, int]:
    """Apply a named style transform to text."""
    return clean(text, app_name=app_name, model_key=model_key, transform=transform_type)


def warmup(model_key: str = DEFAULT_LLM_MODEL) -> None:
    """Pre-load model and run a fast warm-up token generation."""
    clean("warm up test dictation", "default", model_key=model_key)


def cleanup_llm() -> None:
    """Safely release Llama model instances on app exit."""
    with _LLM_LOCK:
        for key in list(_LLM_INSTANCES.keys()):
            inst = _LLM_INSTANCES.pop(key, None)
            if inst is not None:
                try:
                    del inst
                except Exception:
                    pass


atexit.register(cleanup_llm)
