"""
Shared Whisper transcription engine using faster-whisper.

All models are cached locally in the project's cache/models/ directory.
Uses int8 quantization on CPU — fast on Apple Silicon ARM NEON.
"""

import re
import sys
import threading
from pathlib import Path
from typing import Optional

import numpy as np

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
if str(CONFIG_DIR) not in sys.path:
    sys.path.insert(0, str(CONFIG_DIR))

from faster_whisper import WhisperModel  # noqa: E402

from config import DEFAULT_MODEL, MODELS_CACHE_DIR  # noqa: E402

# ---------------------------------------------------------------------------
# Available models
# ---------------------------------------------------------------------------
AVAILABLE_MODELS = [
    "tiny", "tiny.en",
    "base", "base.en",
    "small", "small.en",
    "medium", "medium.en",
    "large-v3", "large-v3-turbo",
    "turbo",
]

MODEL_DISPLAY_ORDER = [
    "tiny.en", "tiny",
    "base.en", "base",
    "small.en", "small",
    "medium.en", "medium",
    "large-v3", "large-v3-turbo",
    "turbo",
]

LIVE_PREVIEW_MODEL_PREFERENCE = ("tiny.en", "tiny", "base.en", "base")

# Silence-hallucination blacklist
_HALLUCINATION_BLACKLIST = frozenset([
    "thank you", "thanks for watching", "subtitle",
    "please subscribe", "the end",
])

# ---------------------------------------------------------------------------
# Thread-safe model cache
# ---------------------------------------------------------------------------
_MODEL_CACHE: dict[str, WhisperModel] = {}
_MODEL_CACHE_LOCK = threading.Lock()
_INFERENCE_LOCKS: dict[str, threading.Lock] = {}


def get_installed_models() -> list[str]:
    """Return all model names. faster-whisper downloads on demand."""
    return list(MODEL_DISPLAY_ORDER)


def get_default_model_name() -> str:
    return DEFAULT_MODEL if DEFAULT_MODEL in AVAILABLE_MODELS else "turbo"


def get_preview_model_name(selected_model: Optional[str] = None) -> str:
    """Return the fastest available model suitable for live preview."""
    installed = get_installed_models()
    for candidate in LIVE_PREVIEW_MODEL_PREFERENCE:
        if candidate in installed:
            return candidate
    preferred = (selected_model or "").strip()
    if preferred in installed:
        return preferred
    return installed[0] if installed else "tiny.en"


def get_model_by_name(model_name: str) -> WhisperModel:
    """
    Load (or return cached) a faster-whisper model. Thread-safe.

    Uses:
    - device="cpu" — ctranslate2 doesn't support Metal/MPS on macOS
    - compute_type="int8" — 2x speed, half RAM, negligible accuracy loss
    - download_root=MODELS_CACHE_DIR — keeps models inside the project
    """
    name = model_name.strip()
    if name not in AVAILABLE_MODELS:
        raise ValueError(f"Unknown model '{model_name}'. Available: {AVAILABLE_MODELS}")

    with _MODEL_CACHE_LOCK:
        if name not in _MODEL_CACHE:
            print(f"Loading Whisper model '{name}' (cpu / int8)...")
            _MODEL_CACHE[name] = WhisperModel(
                name,
                device="cpu",
                compute_type="int8",
                download_root=str(MODELS_CACHE_DIR),
            )
        if name not in _INFERENCE_LOCKS:
            _INFERENCE_LOCKS[name] = threading.Lock()

    return _MODEL_CACHE[name]


def get_inference_lock(model_name: str) -> threading.Lock:
    """Return the per-model inference lock (creates one if absent)."""
    name = model_name.strip()
    with _MODEL_CACHE_LOCK:
        if name not in _INFERENCE_LOCKS:
            _INFERENCE_LOCKS[name] = threading.Lock()
    return _INFERENCE_LOCKS[name]


# ---------------------------------------------------------------------------
# Core transcription function
# ---------------------------------------------------------------------------
def transcribe(
    audio: np.ndarray,
    model_name: str = "turbo",
    language: Optional[str] = "en",
    initial_prompt: Optional[str] = None,
    inference_lock: Optional[threading.Lock] = None,
    is_preview: bool = False,
) -> str:
    """
    Transcribe a 16 kHz float32 numpy array.

    Pipeline:
    1. Noise floor guard (skip if RMS < 0.01)
    2. Audio normalization (target RMS 0.15, max 2x boost)
    3. faster-whisper inference with built-in VAD filter
    4. Segment confidence filtering (no_speech_prob + avg_logprob)
    5. Hallucination blacklist + bigram loop detection

    Args:
        audio: Float32 numpy array at 16 kHz mono.
        model_name: Whisper model variant to use.
        language: ISO-639-1 code (None = auto-detect).
        initial_prompt: Custom vocabulary hint for Whisper.
        inference_lock: Optional external lock to serialize model access.
        is_preview: If True, use relaxed thresholds for lower latency.

    Returns:
        Cleaned transcript string, or "" if no speech detected.
    """
    if audio is None or audio.size == 0:
        return ""

    # 1. Noise floor guard
    rms = float(np.sqrt(np.mean(audio ** 2)))
    if rms < 0.01:
        return ""

    # 2. Normalize audio amplitude
    if rms > 0.005:
        scale = min(0.15 / rms, 2.0)
        audio = np.clip(audio * scale, -1.0, 1.0).astype(np.float32)

    # 3. Transcription
    model = get_model_by_name(model_name)
    lock = inference_lock or get_inference_lock(model_name)

    transcribe_kwargs: dict = dict(
        language=language,
        initial_prompt=initial_prompt,
        beam_size=5,
        best_of=5,
        temperature=0,
        no_speech_threshold=0.6,
        log_prob_threshold=-1.0,
        compression_ratio_threshold=2.4,
        condition_on_previous_text=False,
        vad_filter=True,
        vad_parameters={"threshold": 0.5, "min_silence_duration_ms": 300},
    )

    if is_preview:
        # Faster settings for live preview
        transcribe_kwargs.update(beam_size=1, best_of=1)

    with lock:
        segments_gen, _info = model.transcribe(audio, **transcribe_kwargs)
        segments = list(segments_gen)  # consume the generator

    # 4. Segment confidence filtering
    if not is_preview:
        segments = [
            seg for seg in segments
            if seg.no_speech_prob < 0.2 and seg.avg_logprob > -0.5
        ]

    raw_text = " ".join(seg.text.strip() for seg in segments).strip()

    if len(raw_text) < 3:
        return ""

    # 5. Hallucination defense
    cleaned_lower = re.sub(r"[^\w\s]", "", raw_text.lower()).strip()

    if cleaned_lower in _HALLUCINATION_BLACKLIST:
        return ""

    words = cleaned_lower.split()
    if len(words) >= 4:
        phrase_counts: dict[str, int] = {}
        for i in range(len(words) - 1):
            p = f"{words[i]} {words[i + 1]}"
            phrase_counts[p] = phrase_counts.get(p, 0) + 1
        if any(count > 2 for count in phrase_counts.values()):
            return ""

    return raw_text.strip()


def warmup(model_name: str = "turbo") -> None:
    """
    Pre-load a model and run a silent transcription to warm up internal buffers.
    Call at app startup to avoid first-use latency.
    """
    model = get_model_by_name(model_name)
    silence = np.zeros(16_000, dtype=np.float32)
    lock = get_inference_lock(model_name)
    with lock:
        segments_gen, _ = model.transcribe(silence, language="en", vad_filter=False)
        list(segments_gen)
