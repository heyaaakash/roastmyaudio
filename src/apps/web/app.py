"""
RoastMyAudio Flow Dashboard & Web API Server.

Serves the Wispr Flow-inspired Desktop Dashboard and provides
full REST APIs for audio recording management, retrying LLM cleanups,
re-transcriptions, style transforms, and dictionary management.
"""

import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from flask import Flask, jsonify, render_template, request, send_file
from flask_cors import CORS

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SRC_DIR = Path(__file__).resolve().parent.parent.parent
for _p in (str(PROJECT_ROOT), str(SRC_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config import FLASK_HOST, FLASK_PORT, RECORDINGS_DIR, TEMP_UPLOADS_DIR  # noqa: E402
from src.shared.dictionary import add as add_dict_word  # noqa: E402
from src.shared.dictionary import as_prompt  # noqa: E402
from src.shared.dictionary import load as load_dictionary  # noqa: E402
from src.shared.dictionary import remove as remove_dict_word  # noqa: E402
from src.shared.formatter import (  # noqa: E402
    filter_hallucinations,
    format_transcript,
    format_transcript_strict,
)
from src.shared.history import (  # noqa: E402
    delete_recording,
    dismiss_recording,
    get_history,
    get_recording,
    get_stats,
    recover_recording,
    save_recording,
    update_recording,
)
from src.shared.llm_cleanup import clean as llm_clean  # noqa: E402
from src.shared.retry_engine import (  # noqa: E402
    retranscribe_recording,
    retry_cleanup,
)
from src.shared.settings import load as load_settings  # noqa: E402
from src.shared.settings import set as update_setting  # noqa: E402
from src.shared.transcriber import (  # noqa: E402
    get_default_model_name,
    get_inference_lock,
    get_installed_models,
    get_preview_model_name,
    transcribe,
)

# ---------------------------------------------------------------------------
# Flask app configuration
# ---------------------------------------------------------------------------
app = Flask(
    __name__,
    template_folder=Path(__file__).resolve().parent / "templates",
    static_folder=Path(__file__).resolve().parent / "static",
)
CORS(app)

TEMP_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

LIVE_PREVIEW_WORD_LIMIT = 6


def _tail_words(text: str, limit: int = LIVE_PREVIEW_WORD_LIMIT) -> str:
    words = text.split()
    return " ".join(words[-limit:]) if words else ""


# ---------------------------------------------------------------------------
# Web Page Route
# ---------------------------------------------------------------------------
@app.get("/")
def index():
    """Render the Wispr Flow-style dashboard interface."""
    return render_template("index.html")


# ---------------------------------------------------------------------------
# History & Audio API Routes
# ---------------------------------------------------------------------------
@app.get("/api/history")
def api_history():
    """Get list of recording sessions with optional text search and status filter."""
    q = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "all").strip()
    limit = int(request.args.get("limit", 100))
    recordings = get_history(search_query=q or None, status_filter=status_filter or None, limit=limit)
    return jsonify({"recordings": recordings, "count": len(recordings)})


@app.get("/api/audio/<recording_id>")
def api_audio(recording_id: str):
    """Stream audio WAV file for browser playback."""
    rec = get_recording(recording_id)
    if not rec:
        return jsonify({"error": "Recording not found"}), 404

    audio_file = rec.get("audio_file")
    if not audio_file:
        return jsonify({"error": "No audio file for this recording"}), 404

    audio_path = RECORDINGS_DIR / audio_file
    if not audio_path.exists():
        return jsonify({"error": "Audio file not found on disk"}), 404

    return send_file(str(audio_path), mimetype="audio/wav")


@app.post("/api/retry_cleanup/<recording_id>")
def api_retry_cleanup(recording_id: str):
    """Re-run LLM cleanup or style transform on an existing recording."""
    data = request.get_json(silent=True) or {}
    style = data.get("style", "clean")
    model_key = data.get("model", "qwen2.5-0.5b")

    try:
        updated = retry_cleanup(recording_id, transform_style=style, model_key=model_key)
        return jsonify({"success": True, "recording": updated})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Retry cleanup failed: {exc}"}), 500


@app.post("/api/retry_transcribe/<recording_id>")
def api_retry_transcribe(recording_id: str):
    """Re-transcribe the saved audio recording with a selected Whisper model/language."""
    data = request.get_json(silent=True) or {}
    model_name = data.get("model") or get_default_model_name()
    language = data.get("language") or "en"
    run_llm = data.get("run_llm", True)
    llm_model = data.get("llm_model", "qwen2.5-0.5b")

    try:
        updated = retranscribe_recording(
            recording_id=recording_id,
            model_name=model_name,
            language=language,
            run_llm=run_llm,
            llm_model=llm_model,
        )
        return jsonify({"success": True, "recording": updated})
    except (ValueError, FileNotFoundError) as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Re-transcribe failed: {exc}"}), 500


@app.post("/api/transform/<recording_id>")
def api_transform(recording_id: str):
    """Apply a named transform (formal, casual, bullets, concise, meeting_notes)."""
    data = request.get_json(silent=True) or {}
    transform_type = data.get("transform", "formal")
    model_key = data.get("model", "qwen2.5-0.5b")

    try:
        updated = retry_cleanup(recording_id, transform_style=transform_type, model_key=model_key)
        return jsonify({"success": True, "recording": updated})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.post("/api/history/<recording_id>/dismiss")
def api_dismiss(recording_id: str):
    """Dismiss a recording entry."""
    success = dismiss_recording(recording_id)
    return jsonify({"success": success})


@app.post("/api/history/<recording_id>/recover")
def api_recover(recording_id: str):
    """Recover a dismissed recording entry."""
    success = recover_recording(recording_id)
    return jsonify({"success": success})


@app.post("/api/history/<recording_id>/flag")
def api_flag(recording_id: str):
    """Toggle flag on a recording."""
    rec = get_recording(recording_id)
    if not rec:
        return jsonify({"error": "Recording not found"}), 404
    flagged = not rec.get("flagged", False)
    updated = update_recording(recording_id, {"flagged": flagged})
    return jsonify({"success": True, "recording": updated})


@app.delete("/api/history/<recording_id>")
def api_delete_recording(recording_id: str):
    """Delete a recording entry and associated audio."""
    success = delete_recording(recording_id)
    return jsonify({"success": success})


@app.get("/api/stats")
def api_stats():
    """Get aggregated statistics."""
    return jsonify(get_stats())


# ---------------------------------------------------------------------------
# Dictionary & Settings APIs
# ---------------------------------------------------------------------------
@app.get("/api/dictionary")
def api_get_dictionary():
    """List custom dictionary vocabulary."""
    return jsonify({"words": load_dictionary()})


@app.post("/api/dictionary")
def api_add_dictionary():
    """Add a custom word/phrase to dictionary."""
    data = request.get_json(silent=True) or {}
    word = data.get("word", "").strip()
    if not word:
        return jsonify({"error": "Word cannot be empty"}), 400
    add_dict_word(word)
    return jsonify({"success": True, "words": load_dictionary()})


@app.delete("/api/dictionary/<path:word>")
def api_remove_dictionary(word: str):
    """Remove a word from custom dictionary."""
    remove_dict_word(word)
    return jsonify({"success": True, "words": load_dictionary()})


@app.get("/api/settings")
def api_get_settings():
    """Get all settings."""
    return jsonify(load_settings())


@app.post("/api/settings")
def api_update_settings():
    """Update settings."""
    data = request.get_json(silent=True) or {}
    for k, v in data.items():
        try:
            update_setting(k, v)
        except Exception:
            pass
    return jsonify({"success": True, "settings": load_settings()})


@app.get("/api/models")
@app.get("/models")
def models():
    """Get available models."""
    return jsonify({
        "models": get_installed_models(),
        "default_model": get_default_model_name(),
    })


# ---------------------------------------------------------------------------
# Live Web Recording / Transcription Routes
# ---------------------------------------------------------------------------
@app.post("/transcribe")
def transcribe_route():
    """Full transcription of an uploaded audio file from browser."""
    audio_file = request.files.get("audio")
    if audio_file is None:
        return jsonify({"error": "No audio file provided."}), 400

    suffix = Path(audio_file.filename or "recording.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(
        dir=TEMP_UPLOADS_DIR, suffix=suffix, delete=False
    ) as tmp:
        audio_path = Path(tmp.name)
        audio_file.save(tmp)

    try:
        model_name = (request.form.get("model") or "").strip() or get_default_model_name()
        strict_mode = (request.form.get("strict_mode") or "").lower() == "true"
        app_name = (request.form.get("app") or "").strip() or "Web Flow"
        initial_prompt = as_prompt() or None

        # Transcribe audio
        raw_text = transcribe(
            audio_path,
            model_name=model_name,
            language="en",
            initial_prompt=initial_prompt,
            inference_lock=get_inference_lock(model_name),
        )

        raw_text = filter_hallucinations(raw_text)
        formatter_start = perf_counter()
        if strict_mode:
            formatted_text = format_transcript_strict(raw_text)
            llm_ms = round((perf_counter() - formatter_start) * 1000, 3)
            cleaned_text = raw_text
        else:
            cleaned_text, llm_ms = llm_clean(raw_text, app_name=app_name)
            formatted_text = format_transcript(cleaned_text)

        # Save to history & recordings
        rec = save_recording(
            audio=None,
            raw=raw_text,
            cleaned=cleaned_text,
            formatted=formatted_text,
            app=app_name,
            latency_ms=int(llm_ms),
            model_used=model_name,
        )

        return jsonify({
            "text": formatted_text,
            "raw_text": raw_text,
            "cleaned_text": cleaned_text,
            "saved_path": str(audio_path),
            "formatter_ms": llm_ms,
            "model_used": model_name,
            "recording_id": rec.get("id"),
            "transcribed_at_utc": datetime.now(timezone.utc).isoformat(),
        })
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Transcription failed: {exc}"}), 500


@app.post("/transcribe_partial")
def transcribe_partial_route():
    """Live-preview transcription."""
    audio_file = request.files.get("audio")
    if audio_file is None:
        return jsonify({"error": "No audio file provided."}), 400

    suffix = Path(audio_file.filename or "preview.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(
        dir=TEMP_UPLOADS_DIR, suffix=suffix, delete=False
    ) as tmp:
        audio_path = Path(tmp.name)
        audio_file.save(tmp)

    try:
        model_name = (request.form.get("model") or "").strip() or get_default_model_name()
        preview_model = get_preview_model_name(model_name)

        raw_text = transcribe(
            audio_path,
            model_name=preview_model,
            language="en",
            inference_lock=get_inference_lock(preview_model),
            is_preview=True,
        )
        raw_text = filter_hallucinations(raw_text)
        preview_text = _tail_words(raw_text)

        return jsonify({
            "preview_text": preview_text,
            "raw_text": raw_text,
            "model_used": preview_model,
            "transcribed_at_utc": datetime.now(timezone.utc).isoformat(),
        })
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Live preview failed: {exc}"}), 500


if __name__ == "__main__":
    print(f"🎙️ RoastMyAudio Flow Dashboard running on http://{FLASK_HOST}:{FLASK_PORT}")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False)
