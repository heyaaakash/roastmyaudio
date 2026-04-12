"""
WhisperFlow Web UI — Flask server.

Provides two transcription endpoints:
  POST /transcribe         — full transcription of an audio file
  POST /transcribe_partial — live-preview transcription (low latency)

Models are loaded lazily and cached in memory. All cache artifacts are
written to the project-local cache/ directory — nothing goes to ~/.cache.
"""

import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

# ---------------------------------------------------------------------------
# Path setup — must run before project imports
# ---------------------------------------------------------------------------
CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
SRC_DIR = Path(__file__).resolve().parent.parent
for _p in (str(CONFIG_DIR), str(SRC_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config import TEMP_UPLOADS_DIR, FLASK_HOST, FLASK_PORT  # noqa: E402
from shared.transcriber import (  # noqa: E402
    get_installed_models,
    get_default_model_name,
    get_model_by_name,
    get_inference_lock,
    get_preview_model_name,
    transcribe,
)
from shared.formatter import (  # noqa: E402
    format_transcript,
    format_transcript_strict,
    filter_hallucinations,
)
from shared.dictionary import as_prompt  # noqa: E402
from shared.history import save as save_history  # noqa: E402

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(
    __name__,
    template_folder=Path(__file__).resolve().parent / "templates",
    static_folder=Path(__file__).resolve().parent / "static",
)
CORS(app)

TEMP_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

LIVE_PREVIEW_WORD_LIMIT = 6


def _tail_words(text: str, limit: int = LIVE_PREVIEW_WORD_LIMIT) -> str:
    words = text.split()
    return " ".join(words[-limit:]) if words else ""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/")
def index():
    return render_template("index.html")


@app.get("/models")
def models():
    return jsonify({
        "models": get_installed_models(),
        "default_model": get_default_model_name(),
    })


@app.post("/transcribe")
def transcribe_route():
    """Full transcription of an uploaded audio file."""
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

        initial_prompt = as_prompt() or None

        # Transcribe using the shared engine
        raw_text = transcribe(
            audio_path,           # faster-whisper also accepts file paths
            model_name=model_name,
            language="en",
            initial_prompt=initial_prompt,
            inference_lock=get_inference_lock(model_name),
        )

        # Post-filter and format
        raw_text = filter_hallucinations(raw_text)
        formatter_start = perf_counter()
        formatted_text = format_transcript_strict(raw_text) if strict_mode else format_transcript(raw_text)
        formatter_ms = round((perf_counter() - formatter_start) * 1000, 3)

        app_name = (request.form.get("app") or "").strip() or "unknown"
        save_history(raw_text, formatted_text, app_name, formatter_ms)

        return jsonify({
            "text": formatted_text,
            "raw_text": raw_text,
            "saved_path": str(audio_path),
            "formatter_ms": formatter_ms,
            "model_used": model_name,
            "transcribed_at_utc": datetime.now(timezone.utc).isoformat(),
        })
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Transcription failed: {exc}"}), 500


@app.post("/transcribe_partial")
def transcribe_partial_route():
    """Live-preview transcription — returns last N words for low-latency overlay."""
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
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Live preview failed: {exc}"}), 500


if __name__ == "__main__":
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False)
