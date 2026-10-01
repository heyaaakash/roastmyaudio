"""
Retry and Re-generation Engine for RoastMyAudio.
Allows re-transcribing saved audio recordings with different Whisper models
or re-running LLM cleanups and style transforms.
"""

import sys
from pathlib import Path

# Add config and shared directory to path
CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
SRC_DIR = Path(__file__).resolve().parent.parent
for _p in (str(CONFIG_DIR), str(SRC_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config import RECORDINGS_DIR  # noqa: E402
from src.shared.formatter import filter_hallucinations, format_transcript  # noqa: E402
from src.shared.history import get_recording, update_recording  # noqa: E402
from src.shared.llm_cleanup import clean, transform_text  # noqa: E402
from src.shared.transcriber import get_inference_lock, transcribe  # noqa: E402


def retranscribe_recording(
    recording_id: str,
    model_name: str = "base",
    language: str | None = "en",
    run_llm: bool = True,
    llm_model: str = "qwen2.5-0.5b",
) -> dict:
    """
    Re-transcribe a saved audio recording from disk.

    Args:
        recording_id: Unique recording ID in history
        model_name: Whisper model to use ('tiny', 'base', 'small', 'medium')
        language: Language code (e.g. 'en', 'es', 'fr' or None for auto)
        run_llm: Whether to run LLM cleanup on result
        llm_model: LLM model identifier

    Returns:
        Updated recording dictionary
    """
    rec = get_recording(recording_id)
    if not rec:
        raise ValueError(f"Recording {recording_id} not found")

    audio_file = rec.get("audio_file")
    if not audio_file:
        raise ValueError(f"No audio file associated with recording {recording_id}")

    audio_path = RECORDINGS_DIR / audio_file
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file {audio_path} does not exist on disk")

    # Transcribe saved audio file
    raw_text = transcribe(
        audio_path,
        model_name=model_name,
        language=language,
        inference_lock=get_inference_lock(model_name),
    )
    raw_text = filter_hallucinations(raw_text)

    from src.shared.formatter import format_transcript_strict
    from src.shared.personalization import apply, style_for

    app_name = rec.get("app", "General")
    corrected, snippet = apply(raw_text)
    style = style_for(app_name)
    if run_llm and not snippet and style != "verbatim" and len(corrected.split()) >= 3:
        cleaned_text, latency_ms = clean(
            corrected,
            app_name=app_name,
            model_key=llm_model,
            transform="clean" if style == "default" else style,
        )
    else:
        cleaned_text, latency_ms = corrected, 0
    formatted = (
        cleaned_text
        if snippet
        else format_transcript_strict(cleaned_text)
        if style == "verbatim"
        else format_transcript(cleaned_text)
    )

    words = [w for w in formatted.split() if w.strip()]
    dur = rec.get("duration_sec", 0.0)
    wpm = int(len(words) / (dur / 60.0)) if dur > 0.5 else rec.get("wpm", 0)

    updates = {
        "raw": raw_text,
        "cleaned": cleaned_text,
        "formatted": formatted,
        "model_used": model_name,
        "llm_model": llm_model,
        "latency_ms": latency_ms,
        "word_count": len(words),
        "wpm": wpm,
        "status": "completed",
    }

    updated = update_recording(recording_id, updates)
    return updated or rec


def retry_cleanup(
    recording_id: str,
    transform_style: str = "clean",
    model_key: str = "qwen2.5-0.5b",
) -> dict:
    """
    Re-run LLM cleanup or style transform on the recording's raw transcript.
    """
    rec = get_recording(recording_id)
    if not rec:
        raise ValueError(f"Recording {recording_id} not found")

    raw_text = rec.get("raw") or rec.get("formatted") or ""
    if not raw_text:
        raise ValueError("No raw transcript available for this recording")

    app_name = rec.get("app", "General")

    if transform_style == "clean":
        cleaned_text, latency_ms = clean(
            raw_text, app_name=app_name, model_key=model_key, transform="clean"
        )
        formatted = format_transcript(cleaned_text)
    else:
        cleaned_text, latency_ms = transform_text(
            raw_text, transform_type=transform_style, app_name=app_name, model_key=model_key
        )
        formatted = cleaned_text

    words = [w for w in formatted.split() if w.strip()]
    dur = rec.get("duration_sec", 0.0)
    wpm = int(len(words) / (dur / 60.0)) if dur > 0.5 else rec.get("wpm", 0)

    transforms = rec.get("transforms") or {}
    transforms[transform_style] = formatted

    updates = {
        "cleaned": cleaned_text,
        "formatted": formatted,
        "llm_model": model_key,
        "latency_ms": latency_ms,
        "word_count": len(words),
        "wpm": wpm,
        "transforms": transforms,
        "cleanup_applied": latency_ms > 0,
        "status": "completed",
    }

    updated = update_recording(recording_id, updates)
    return updated or rec
