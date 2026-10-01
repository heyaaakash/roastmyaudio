"""
History and audio recordings storage module.
Persists transcription history and audio WAV files locally in data/.
"""

import json
import sys
import uuid
import wave
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from src.shared.storage import synchronized, write_json

# Add config directory to path
CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
if str(CONFIG_DIR) not in sys.path:
    sys.path.insert(0, str(CONFIG_DIR))

from config import HISTORY_PATH, RECORDINGS_DIR, SAMPLE_RATE  # noqa: E402

RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)


def _format_display_time(dt: datetime) -> str:
    """Format time like '7:33 pm'."""
    hour = dt.strftime("%I").lstrip("0")
    if not hour:
        hour = "12"
    minute = dt.strftime("%M")
    ampm = dt.strftime("%p").lower()
    return f"{hour}:{minute} {ampm}"


def _get_date_group(dt: datetime) -> str:
    """Classify datetime into 'TODAY', 'YESTERDAY', or formatted date like 'August 14'."""
    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day)
    yesterday_start = today_start - timedelta(days=1)

    if dt >= today_start:
        return "TODAY"
    elif dt >= yesterday_start:
        return "YESTERDAY"
    else:
        return dt.strftime("%B %d, %Y")


def _write_wav_file(audio: np.ndarray, wav_path: Path, sample_rate: int = SAMPLE_RATE):
    """Write float32 numpy audio array to 16-bit PCM WAV file."""
    if audio is None or audio.size == 0:
        return
    # Convert float32 [-1.0, 1.0] to int16 [-32768, 32767]
    clipped = np.clip(audio, -1.0, 1.0)
    pcm_data = (clipped * 32767).astype(np.int16)
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 2 bytes per sample = 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data.tobytes())


@synchronized(lambda: HISTORY_PATH)
def save_recording(
    audio: np.ndarray | None = None,
    raw: str = "",
    cleaned: str = "",
    app: str = "General",
    latency_ms: int = 0,
    model_used: str = "base",
    llm_model: str = "qwen2.5-0.5b",
    duration_sec: float | None = None,
    formatted: str | None = None,
    status: str = "completed",
    recording_id: str | None = None,
) -> dict:
    """
    Save audio recording file and record full session metadata in history.
    """
    now = datetime.now()
    rec_id = recording_id or f"rec_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    # Save audio WAV if provided
    audio_file_name = None
    if audio is not None and audio.size > 0:
        audio_file_name = f"{rec_id}.wav"
        wav_path = RECORDINGS_DIR / audio_file_name
        _write_wav_file(audio, wav_path, SAMPLE_RATE)
        if duration_sec is None or duration_sec <= 0:
            duration_sec = round(float(audio.size) / SAMPLE_RATE, 2)

    final_formatted = formatted if formatted is not None else (cleaned or raw)
    words = [w for w in final_formatted.split() if w.strip()]
    word_count = len(words)
    wpm = int(word_count / (duration_sec / 60.0)) if (duration_sec and duration_sec > 0.5) else 0

    entry = {
        "id": rec_id,
        "timestamp": now.isoformat(),
        "date_group": _get_date_group(now),
        "display_time": _format_display_time(now),
        "app": app or "General",
        "raw": raw,
        "raw_text": raw,
        "cleaned": cleaned or raw,
        "cleaned_text": cleaned or raw,
        "formatted": final_formatted,
        "formatted_text": final_formatted,
        "latency_ms": latency_ms,
        "duration_sec": round(duration_sec or 0.0, 2),
        "model_used": model_used,
        "llm_model": llm_model,
        "audio_file": audio_file_name,
        "status": status,
        "word_count": word_count,
        "wpm": wpm,
        "flagged": False,
        "transforms": {},
    }

    entries = load()
    entries.insert(0, entry)
    _persist_history(entries)
    return entry


def save(raw: str, cleaned: str, app: str, latency_ms: int):
    """Backwards compatibility helper."""
    save_recording(
        audio=None,
        raw=raw,
        cleaned=cleaned,
        app=app,
        latency_ms=latency_ms,
    )


@synchronized(lambda: HISTORY_PATH)
def load() -> list[dict]:
    """Load all history entries."""
    if not HISTORY_PATH.exists():
        return []
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            migrated = False
            # Ensure each entry has an id and date_group for UI
            for item in data:
                if "id" not in item:
                    migrated = True
                    item["id"] = f"legacy_{uuid.uuid4().hex[:8]}"
                if "status" not in item:
                    item["status"] = "completed"
                if "date_group" not in item and "timestamp" in item:
                    try:
                        dt = datetime.fromisoformat(item["timestamp"])
                        item["date_group"] = _get_date_group(dt)
                        item["display_time"] = _format_display_time(dt)
                    except Exception:
                        item["date_group"] = "TODAY"
            if migrated:
                _persist_history(data)
            return data
        return []
    except Exception:
        return []


def _persist_history(entries: list[dict]):
    """Persist history entries to disk."""
    write_json(HISTORY_PATH, entries)


def latest() -> dict | None:
    """Get the most recent history entry."""
    entries = load()
    return entries[0] if entries else None


def get_recording(recording_id: str) -> dict | None:
    """Find a specific recording by ID."""
    entries = load()
    for item in entries:
        if item.get("id") == recording_id:
            return item
    return None


@synchronized(lambda: HISTORY_PATH)
def update_recording(recording_id: str, updates: dict) -> dict | None:
    """Update fields of an existing recording."""
    entries = load()
    target = None
    for item in entries:
        if item.get("id") == recording_id:
            item.update(updates)
            target = item
            break
    if target is not None:
        _persist_history(entries)
    return target


def dismiss_recording(recording_id: str) -> bool:
    """Mark recording as dismissed."""
    res = update_recording(recording_id, {"status": "dismissed"})
    return res is not None


def recover_recording(recording_id: str) -> bool:
    """Recover a dismissed recording."""
    res = update_recording(recording_id, {"status": "completed"})
    return res is not None


@synchronized(lambda: HISTORY_PATH)
def delete_recording(recording_id: str) -> bool:
    """Delete a recording entry and its audio file."""
    entries = load()
    found = False
    new_entries = []
    for item in entries:
        if item.get("id") == recording_id:
            found = True
            audio_file = item.get("audio_file")
            if audio_file:
                wav_path = RECORDINGS_DIR / audio_file
                if wav_path.exists():
                    try:
                        wav_path.unlink()
                    except Exception:
                        pass
        else:
            new_entries.append(item)
    if found:
        _persist_history(new_entries)
    return found


def get_history(
    search_query: str | None = None,
    status_filter: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """
    Query recordings with optional text search and status filter.
    Returns grouped list ready for timeline rendering.
    """
    entries = load()
    filtered = []
    q = (search_query or "").strip().lower()

    for item in entries:
        if status_filter and status_filter != "all":
            if item.get("status") != status_filter:
                continue

        if q:
            raw_text = (item.get("raw") or "").lower()
            cleaned_text = (item.get("cleaned") or "").lower()
            formatted_text = (item.get("formatted") or "").lower()
            app_text = (item.get("app") or "").lower()
            if q not in raw_text and q not in cleaned_text and q not in formatted_text and q not in app_text:
                continue

        # Refresh date_group relative to current time
        if "timestamp" in item:
            try:
                dt = datetime.fromisoformat(item["timestamp"])
                item["date_group"] = _get_date_group(dt)
                item["display_time"] = _format_display_time(dt)
            except Exception:
                pass

        filtered.append(item)

    return filtered[:limit]


def get_stats() -> dict:
    """Report actual activity; an empty workspace always starts at zero."""
    entries = [item for item in load() if item.get("status") != "dismissed"]
    total_words = 0
    total_duration_sec = 0.0
    timed_words = 0
    active_dates = set()
    for item in entries:
        text = item.get("formatted") or item.get("cleaned") or item.get("raw") or ""
        words = len(text.split())
        total_words += words
        duration = max(0.0, float(item.get("duration_sec") or 0.0))
        total_duration_sec += duration
        if duration > 0:
            timed_words += words
        try:
            active_dates.add(datetime.fromisoformat(item["timestamp"]).date())
        except (KeyError, ValueError, TypeError):
            pass
    day = datetime.now().date()
    if day not in active_dates:
        day -= timedelta(days=1)
    streak_days = 0
    while day in active_dates:
        streak_days += 1
        day -= timedelta(days=1)
    return {
        "total_words": total_words,
        "formatted_words": f"{total_words / 1000:.1f}K" if total_words >= 1000 else str(total_words),
        "avg_wpm": round(timed_words / (total_duration_sec / 60)) if total_duration_sec else 0,
        "streak_days": streak_days,
        "total_recordings": len(entries),
        "total_minutes": round(total_duration_sec / 60.0, 1),
    }


@synchronized(lambda: HISTORY_PATH)
def recover_interrupted():
    """A new owning desktop process can offer saved audio from interrupted inference."""
    entries = load()
    changed = False
    for entry in entries:
        if entry.get("status") == "processing":
            entry["status"] = "failed"
            changed = True
    if changed:
        _persist_history(entries)
