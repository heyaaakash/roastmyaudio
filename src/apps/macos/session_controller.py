"""One capture lifecycle for workspace buttons, menu actions and global shortcuts."""

from __future__ import annotations

import queue
import threading
import time

import numpy as np

from config import SAMPLE_RATE
from src.shared import history, personalization, settings


def process_speech(audio, preferences, target, strict=False):
    from src.shared.context_detector import build_whisper_prompt
    from src.shared.dictionary import load as vocabulary
    from src.shared.formatter import format_transcript, format_transcript_strict
    from src.shared.llm_cleanup import clean
    from src.shared.transcriber import transcribe

    raw = transcribe(
        audio,
        model_name=preferences["model"],
        language=None if preferences["language"] == "auto" else preferences["language"],
        initial_prompt=(
            build_whisper_prompt(
                app_name=target["name"],
                clipboard_text=target.get("context", ""),
                custom_words=vocabulary(),
            )
            if preferences["context_awareness"]
            else ", ".join(vocabulary())
        )
        or None,
    )
    library = personalization.load()
    corrected, snippet = personalization.apply(raw, library)
    style = "verbatim" if strict else personalization.style_for(target["name"], library)
    cleaned, latency = corrected, 0
    if not snippet and style != "verbatim" and preferences["llm_enabled"] and corrected.strip():
        cleaned, latency = clean(
            corrected,
            target["name"],
            model_key=preferences["llm_model"],
            transform="clean" if style == "default" else style,
        )
    if snippet:
        formatted = cleaned
    else:
        formatter = (
            format_transcript
            if preferences["voice_commands"] and style != "verbatim"
            else format_transcript_strict
        )
        formatted = formatter(cleaned)
    return {"raw": raw, "cleaned": cleaned, "formatted": formatted, "latency_ms": latency}


class _SerialWorker:
    def __init__(self):
        self.queue = queue.Queue()
        self.closed = False
        threading.Thread(target=self._run, name="RoastMyAudioSpeech", daemon=True).start()

    def _run(self):
        while True:
            task = self.queue.get()
            if task is None:
                return
            function, args = task
            function(*args)

    def submit(self, function, *args):
        if not self.closed:
            self.queue.put((function, args))

    def shutdown(self, **_):
        self.closed = True
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break
        self.queue.put(None)


class SessionController:
    def __init__(
        self,
        recorder_factory,
        capture_target,
        insert_text,
        notify=None,
        processor=process_speech,
        preferences=settings.load,
        clock=time.monotonic,
    ):
        self._recorder_factory = recorder_factory
        self._capture_target = capture_target
        self._insert = insert_text
        self._notify = notify or (lambda _: None)
        self._processor = processor
        self._preferences = preferences
        self._clock = clock
        self._lock = threading.RLock()
        self._executor = _SerialWorker()
        self._closed = False
        self._generation = 0
        self._recorder = None
        self._limit = None
        self._audio = None
        self._recording_id = None
        self._state = {
            "phase": "idle",
            "message": "Ready when you are",
            "text": "",
            "error": "",
            "can_retry": False,
            "level": 0,
            "seconds": 0,
            "source": "",
            "recording_id": None,
        }

    def snapshot(self):
        with self._lock:
            state = dict(self._state)
            if state["phase"] == "recording":
                state["seconds"] = max(0, self._clock() - self._started)
            return state

    def _publish(self, **changes):
        self._state.update(changes)
        try:
            self._notify(self.snapshot())
        except Exception:
            pass

    def start(self, source="workspace", strict=False, practice=False):
        if source not in {"workspace", "menu", "hotkey"}:
            raise ValueError("Unknown recording source")
        with self._lock:
            if self._closed:
                raise ValueError("The app is quitting")
            if self._state["phase"] in {"recording", "processing", "preparing"}:
                raise ValueError("Finish the current session first")
            if self._state["can_retry"]:
                raise ValueError("Retry or discard your previous recording first")
            self._generation += 1
            self._prefs = dict(self._preferences())
            self._target = (
                self._capture_target()
                if source != "workspace" and not practice
                else {"name": "Practice" if practice else "Workspace", "bundle": "", "pid": None}
            )
            self._source, self._strict, self._practice = source, strict, practice
            self._recording_id, self._audio = None, None
            self._recorder = self._recorder_factory(device_id=self._prefs["device_id"])
            self._started = self._clock()
            try:
                self._recorder.start(extra_callback=self._on_audio)
            except Exception:
                try:
                    self._recorder.stop()
                except Exception:
                    pass
                finally:
                    self._recorder = None
                self._publish(
                    phase="error",
                    message="Couldn't open the microphone",
                    error="Check microphone permission and your selected input. Reconnect the microphone or choose System Default in Preferences.",
                    can_retry=False,
                )
                return self.snapshot()
            self._publish(
                phase="recording",
                message="Listening",
                text="",
                error="",
                can_retry=False,
                source=source,
                practice=practice,
                recording_id=None,
                seconds=0,
            )
            self._limit = threading.Timer(300, self.stop)
            self._limit.daemon = True
            self._limit.start()
            return self.snapshot()

    def _on_audio(self, chunk):
        if not self._lock.acquire(blocking=False):
            return
        try:
            if self._state["phase"] != "recording":
                return
            # Level updates are throttled; no second inference/preview pipeline.
            now = self._clock()
            if now - getattr(self, "_last_meter", 0) < 0.1:
                return
            self._last_meter = now
            level = min(1.0, float(np.sqrt(np.mean(chunk**2))) / 0.08) if chunk.size else 0
            self._publish(level=level)
        finally:
            self._lock.release()

    def _stop_capture(self):
        if self._limit:
            self._limit.cancel()
            self._limit = None
        recorder, self._recorder = self._recorder, None
        if recorder is None:
            return np.zeros(0, dtype=np.float32)
        return recorder.stop()

    def stop(self):
        with self._lock:
            if self._state["phase"] != "recording":
                return self.snapshot()
            try:
                audio = self._stop_capture()
            except Exception:
                self._publish(
                    phase="error",
                    level=0,
                    message="Recording interrupted",
                    error="The input disconnected. Reconnect it and try again.",
                    can_retry=False,
                )
                return self.snapshot()
            if audio.size < SAMPLE_RATE // 2:
                self._publish(
                    phase="idle", level=0, message="Try speaking for a moment longer", seconds=0
                )
                return self.snapshot()
            self._audio = audio[: SAMPLE_RATE * 300].copy()
            # Save before inference so failures/restarts retain recoverable audio.
            try:
                record = history.save_recording(
                    audio=self._audio,
                    app=self._target["name"],
                    model_used=self._prefs["model"],
                    llm_model=self._prefs["llm_model"],
                    status="processing",
                )
                self._recording_id = record["id"]
            except Exception:
                self._publish(
                    phase="error",
                    level=0,
                    message="Couldn't save this recording",
                    error="Check available disk space. Audio is kept in memory for retry while the app stays open.",
                    can_retry=True,
                )
                return self.snapshot()
            self._submit()
            return self.snapshot()

    def _submit(self):
        self._publish(
            phase="processing",
            level=0,
            message="Preparing speech model and transcribing locally…",
            error="",
            can_retry=False,
            recording_id=self._recording_id,
        )
        generation = self._generation
        self._executor.submit(
            self._process, generation, self._audio, dict(self._prefs), dict(self._target), self._strict
        )

    def _process(self, generation, audio, preferences, target, strict):
        with self._lock:
            if self._closed or generation != self._generation:
                return
        try:
            result = self._processor(audio, preferences, target, strict)
            with self._lock:
                if self._closed or generation != self._generation:
                    return
                text = result["formatted"].strip()
                if self._recording_id:
                    updated = history.update_recording(
                        self._recording_id,
                        {
                            **result,
                            "raw_text": result["raw"],
                            "cleaned_text": result["cleaned"],
                            "formatted_text": text,
                            "word_count": len(text.split()),
                            "status": "completed" if text else "failed",
                        },
                    )
                    if updated is None:
                        raise ValueError("The recording was removed while processing")
                if not text:
                    self._publish(
                        phase="error",
                        message="No speech recognized",
                        error="Your audio is saved. Check the input or language, then retry.",
                        can_retry=True,
                    )
                    return
                self._publish(
                    phase="idle", text=text, message="Thought captured", can_retry=False, error=""
                )
                self._audio = None
                # UI performs insertion on the main thread after checking the target.
                if self._source != "workspace" and not self._practice:
                    self._insert(text, dict(self._target))
        except Exception:
            with self._lock:
                if self._closed or generation != self._generation:
                    return
                if self._recording_id:
                    try:
                        history.update_recording(self._recording_id, {"status": "failed"})
                    except Exception:
                        pass
                self._publish(
                    phase="error",
                    message="Couldn't transcribe this recording",
                    error="Your audio is saved. Check model availability, disk space and language, then retry or open Recent Thoughts.",
                    can_retry=True,
                )

    def retry(self):
        with self._lock:
            if (
                self._closed
                or self._state["phase"] in {"recording", "processing", "preparing"}
                or self._audio is None
            ):
                raise ValueError("No recording is waiting for retry")
            self._prefs = dict(self._preferences())
            # A retry is review-only; never unexpectedly paste later into another app.
            self._source = "workspace"
            if self._recording_id is None:
                record = history.save_recording(
                    audio=self._audio,
                    app=self._target["name"],
                    model_used=self._prefs["model"],
                    status="processing",
                )
                self._recording_id = record["id"]
            self._submit()
            return self.snapshot()

    def cancel(self):
        with self._lock:
            self._generation += 1
            if self._recorder:
                try:
                    self._stop_capture()
                except Exception:
                    pass
            if self._recording_id and self._state["phase"] in {"processing", "error"}:
                try:
                    history.update_recording(self._recording_id, {"status": "failed"})
                except Exception:
                    pass
            self._audio = None
            self._publish(
                phase="idle",
                level=0,
                seconds=0,
                message="Session canceled; saved history remains",
                text="",
                error="",
                can_retry=False,
            )
            return self.snapshot()

    def prepare(self):
        with self._lock:
            if self._state["phase"] in {"recording", "processing", "preparing"}:
                raise ValueError("Finish the current session first")
            self._publish(
                phase="preparing",
                message="Downloading or initializing your speech model…",
                error="",
            )
            generation = self._generation
            model = self._preferences()["model"]

            def work():
                from src.shared.transcriber import get_model_by_name

                try:
                    get_model_by_name(model)
                    changes = {
                        "phase": "idle",
                        "message": "Speech model ready",
                        "model_ready": model,
                        "error": "",
                    }
                except Exception:
                    changes = {
                        "phase": "error",
                        "message": "Model preparation failed",
                        "error": "Check your connection and available disk space, then try preparing again.",
                    }
                with self._lock:
                    if not self._closed and generation == self._generation:
                        self._publish(**changes)

            self._executor.submit(work)
            return self.snapshot()

    def shutdown(self):
        with self._lock:
            self._closed = True
            self._generation += 1
            if self._recorder:
                try:
                    self._stop_capture()
                except Exception:
                    pass
            self._audio = None
        self._executor.shutdown(wait=False, cancel_futures=True)
