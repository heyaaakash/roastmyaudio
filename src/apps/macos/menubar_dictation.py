"""
WhisperFlow — macOS Menu Bar App.

Hold Fn (or Ctrl+Option+D) to record → release to transcribe and paste.
"""

import logging
import os
import subprocess
import sys
import threading
import time
import warnings
import webbrowser
from pathlib import Path
from typing import Optional

import numpy as np
import rumps
from pynput import keyboard

warnings.filterwarnings("ignore", message=".*upgraded your loaded checkpoint.*")
logging.getLogger("openai").setLevel(logging.ERROR)

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = PROJECT_ROOT / "src"
CONFIG_DIR = PROJECT_ROOT / "config"
for _p in (str(PROJECT_ROOT), str(CONFIG_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Optional macOS framework imports
# ---------------------------------------------------------------------------
try:
    from AppKit import (
        NSEvent,
        NSEventMaskFlagsChanged,
        NSEventModifierFlagFunction,
    )
    from PyObjCTools import AppHelper

    APPKIT_AVAILABLE = True
except Exception:
    APPKIT_AVAILABLE = False

try:
    from ApplicationServices import AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt
except Exception:
    AXIsProcessTrustedWithOptions = None
    kAXTrustedCheckOptionPrompt = None

try:
    from Quartz import (
        CGEventSourceFlagsState,
        CGPreflightListenEventAccess,
        CGRequestListenEventAccess,
        kCGEventFlagMaskSecondaryFn,
        kCGEventSourceStateHIDSystemState,
    )
except Exception:
    CGEventSourceFlagsState = None
    CGPreflightListenEventAccess = None
    CGRequestListenEventAccess = None
    kCGEventFlagMaskSecondaryFn = None
    kCGEventSourceStateHIDSystemState = None

# ---------------------------------------------------------------------------
# Suppress PyAV / Homebrew FFmpeg ObjC warnings at import time
# ---------------------------------------------------------------------------
_old_stderr = os.dup(2)
_devnull = os.open(os.devnull, os.O_WRONLY)
os.dup2(_devnull, 2)
try:
    from src.apps.macos.audio_recorder import (
        SAMPLE_RATE,
        AudioRecorder,
        get_default_input_device,
        list_input_devices,
        normalize_audio,
    )
    from src.apps.macos.hud_overlay import DictationOverlay
    from src.apps.macos.warmup import load_models_async
    from src.shared.dictionary import add as dict_add
    from src.shared.dictionary import as_prompt
    from src.shared.dictionary import load as dict_load
    from src.shared.formatter import format_transcript
    from src.shared.history import load as history_load
    from src.shared.history import save as history_save
    from src.shared.llm_cleanup import clean
    from src.shared.settings import load as settings_load
    from src.shared.settings import set as settings_set
    from src.shared.text_injector import AppMonitor, _write_clipboard, inject
    from src.shared.transcriber import (
        get_installed_models,
        get_preview_model_name,
    )
    from src.shared.transcriber import (
        transcribe as _transcribe_audio,
    )
finally:
    os.dup2(_old_stderr, 2)
    os.close(_devnull)
    os.close(_old_stderr)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FALLBACK_HOLD_HOTKEY = "Ctrl+Option+D"
LIVE_PREVIEW_INTERVAL_SEC = 0.6
LIVE_PREVIEW_WINDOW_SEC = 2.0
LIVE_PREVIEW_MIN_AUDIO_SEC = 0.45
LIVE_PREVIEW_WORD_LIMIT = 6
PTT_STATE_POLL_SEC = 0.12
PTT_MAX_HOLD_SEC = 300
FAST_COMMIT_CHUNK_SEC = 0.35
FAST_COMMIT_POLL_SEC = 0.1
FAST_COMMIT_MIN_TAIL_SEC = 0.1
SHORT_UTTERANCE_FAST_PATH_SEC = 0.8

RUNTIME_DIR = CONFIG_DIR.parent / "data" / "runtime"
RUNTIME_LAST_TEXT_PATH = RUNTIME_DIR / "last_processed.txt"

HOME_URL = "https://github.com/aakashr/open-whisperflow"
UPDATES_URL = "https://github.com/aakashr/open-whisperflow/releases"
HELP_CENTER_URL = "https://github.com/aakashr/open-whisperflow#readme"
SUPPORT_URL = "https://github.com/aakashr/open-whisperflow/discussions"
FEEDBACK_URL = "https://github.com/aakashr/open-whisperflow/issues"

SUPPORTED_LANGUAGES = {
    "Auto-detect": None,
    "English": "en",
    "Spanish": "es",
    "French": "fr",
    "German": "de",
    "Chinese": "zh",
    "Japanese": "ja",
    "Portuguese": "pt",
    "Italian": "it",
    "Korean": "ko",
    "Russian": "ru",
}


# ---------------------------------------------------------------------------
# Main app class
# ---------------------------------------------------------------------------
class WhisperMenuBarApp(rumps.App):
    def __init__(self):
        super().__init__("W")

        # Load persisted settings
        _settings = settings_load()

        self._lock = threading.Lock()
        self._recording = False
        self._audio_recorder: Optional[AudioRecorder] = None
        self._audio_chunks: list[np.ndarray] = []
        self._pressed_keys: set = set()
        self._ptt_active = False
        self._fn_down = False
        self._fallback_down = False
        self._last_processed_text = ""
        self._fn_supported = APPKIT_AVAILABLE
        self._overlay = DictationOverlay() if APPKIT_AVAILABLE else None
        self._fn_monitor_global = None
        self._fn_monitor_local = None
        self._ptt_watchdog_stop_event = threading.Event()
        self._ptt_watchdog_thread: Optional[threading.Thread] = None
        self._ptt_start_time: Optional[float] = None
        self._live_preview_thread: Optional[threading.Thread] = None
        self._live_preview_stop_event = threading.Event()
        self._inference_lock = threading.Lock()
        self._audio_buffer_lock = threading.Lock()
        self._last_live_preview_text = ""
        self._fast_commit_thread: Optional[threading.Thread] = None
        self._fast_commit_stop_event = threading.Event()
        self._fast_chunk_queue: list[np.ndarray] = []
        self._fast_chunk_text_segments: list[str] = []
        self._fast_processed_samples = 0
        self._fast_commit_model_name: Optional[str] = None

        # Settings-backed state
        self._selected_model: str = _settings.get("model", "turbo")
        self._selected_language_label: str = _settings.get("language_label", "English")
        self._selected_language_code: Optional[str] = _settings.get("language", "en")
        self._llm_enabled: bool = _settings.get("llm_enabled", True)

        saved_device = _settings.get("device_id")
        self._selected_input_device: Optional[int] = (
            saved_device if saved_device is not None else get_default_input_device()
        )

        self._keyboard = keyboard.Controller()
        self._model_items: dict[str, rumps.MenuItem] = {}
        self._app_monitor = AppMonitor()

        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

        # ----------------------------------------------------------------
        # Menu construction
        # ----------------------------------------------------------------
        self._status_item = rumps.MenuItem("Status: Idle")
        self._status_item.set_callback(None)

        self._home_item = rumps.MenuItem("Home", callback=self._on_open_home)
        self._updates_item = rumps.MenuItem("Check for updates...", callback=self._on_check_updates)

        self._paste_last_item = rumps.MenuItem("Paste last transcript", callback=self._on_paste_last)
        self._last_preview_item = rumps.MenuItem("No transcript yet")
        self._last_preview_item.set_callback(None)

        self._permissions_item = rumps.MenuItem("Open macOS Permissions", callback=self._on_open_permissions)
        self._dictionary_item = rumps.MenuItem("Personal Dictionary", callback=self._on_show_dictionary)
        self._history_item = rumps.MenuItem("Recent Dictations", callback=self._on_show_history)

        hotkey_hint = (
            "Push-to-talk: hold Fn"
            if self._fn_supported
            else f"Push-to-talk: hold {FALLBACK_HOLD_HOTKEY}"
        )
        self._hotkey_hint_item = rumps.MenuItem(hotkey_hint)
        self._hotkey_hint_item.set_callback(None)

        self._copy_last_item = rumps.MenuItem("Copy Last Processed", callback=self._on_copy_last)
        self._test_overlay_item = rumps.MenuItem("Test Overlay (2s)", callback=self._on_test_overlay)

        # LLM toggle
        llm_label = "LLM Cleanup: ON" if self._llm_enabled else "LLM Cleanup: OFF"
        self._llm_toggle_item = rumps.MenuItem(llm_label, callback=self._on_toggle_llm)

        # Microphone submenu
        self._mic_menu = rumps.MenuItem("Microphone")
        self._mic_items: dict[str, tuple[int, rumps.MenuItem]] = {}
        self._populate_microphone_menu()

        # Language submenu
        self._language_menu = rumps.MenuItem("Language")
        self._language_items: dict[str, rumps.MenuItem] = {}
        self._populate_language_menu()

        # Model submenu
        self._model_menu = rumps.MenuItem("Model")
        installed_models = get_installed_models()
        for model_name in installed_models:
            item = rumps.MenuItem(model_name, callback=self._on_select_model)
            item.state = int(model_name == self._selected_model)
            self._model_menu.add(item)
            self._model_items[model_name] = item

        self._help_item = rumps.MenuItem("Help / Docs", callback=self._on_open_help)
        self._feedback_item = rumps.MenuItem("Report Issue", callback=self._on_open_feedback)
        self._quit_item = rumps.MenuItem("Quit WhisperFlow", callback=self._on_quit)

        self.menu = [
            self._home_item,
            self._updates_item,
            None,
            self._paste_last_item,
            self._last_preview_item,
            None,
            self._hotkey_hint_item,
            None,
            self._mic_menu,
            self._language_menu,
            self._model_menu,
            self._llm_toggle_item,
            None,
            self._dictionary_item,
            self._history_item,
            None,
            self._help_item,
            self._feedback_item,
            None,
            self._status_item,
            self._permissions_item,
            self._copy_last_item,
            self._test_overlay_item,
            None,
            self._quit_item,
        ]

        # ----------------------------------------------------------------
        # Hotkey listeners
        # ----------------------------------------------------------------
        if self._fn_supported:
            self._fn_monitor_global = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                NSEventMaskFlagsChanged, self._on_flags_changed
            )
            self._fn_monitor_local = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
                NSEventMaskFlagsChanged, self._on_flags_changed
            )

        self._hotkey_listener = keyboard.Listener(
            on_press=self._on_key_press, on_release=self._on_key_release
        )
        self._hotkey_listener.start()
        self._start_ptt_watchdog()

        self._check_and_prompt_permissions()
        self._app_monitor.start()

        # Background warmup
        load_models_async(on_complete=self._on_models_ready)

    # ====================================================================
    # Menu population helpers
    # ====================================================================
    def _populate_microphone_menu(self):
        devices = list_input_devices()
        if not devices:
            item = rumps.MenuItem("No input devices found")
            item.set_callback(None)
            self._mic_menu.add(item)
            return
        if self._selected_input_device is None and devices:
            self._selected_input_device = devices[0][0]
        for device_id, label in devices:
            item = rumps.MenuItem(label, callback=self._on_select_microphone)
            item.state = int(device_id == self._selected_input_device)
            self._mic_menu.add(item)
            self._mic_items[label] = (device_id, item)

    def _populate_language_menu(self):
        for label in SUPPORTED_LANGUAGES:
            item = rumps.MenuItem(label, callback=self._on_select_language)
            item.state = int(label == self._selected_language_label)
            self._language_menu.add(item)
            self._language_items[label] = item

    # ====================================================================
    # Status / preview helpers
    # ====================================================================
    def _set_status(self, text: str):
        self._status_item.title = f"Status: {text}"

    def _set_last_preview(self, text: str):
        preview = (text or "").strip()
        if not preview:
            self._last_preview_item.title = "No transcript yet"
            return
        if len(preview) > 42:
            preview = preview[:39].rstrip() + "..."
        self._last_preview_item.title = preview

    def _show_overlay(self):
        if not self._overlay:
            return
        AppHelper.callAfter(self._overlay.show)

    def _hide_overlay(self):
        if not self._overlay:
            return
        AppHelper.callAfter(self._overlay.hide)

    def _set_overlay_preview(self, text: str):
        if not self._overlay:
            return
        AppHelper.callAfter(self._overlay.set_preview_text, text)

    @staticmethod
    def _tail_words(text: str, limit: int = LIVE_PREVIEW_WORD_LIMIT) -> str:
        words = text.split()
        return " ".join(words[-limit:]) if words else ""

    # ====================================================================
    # Permissions
    # ====================================================================
    def _is_accessibility_trusted(self) -> bool:
        if AXIsProcessTrustedWithOptions is None:
            return True
        try:
            return bool(AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: False}))
        except Exception:
            return True

    def _is_input_monitoring_trusted(self) -> bool:
        if CGPreflightListenEventAccess is None:
            return True
        try:
            return bool(CGPreflightListenEventAccess())
        except Exception:
            return True

    def _request_permissions_prompt(self):
        try:
            if AXIsProcessTrustedWithOptions is not None:
                AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})
        except Exception:
            pass
        try:
            if CGRequestListenEventAccess is not None:
                CGRequestListenEventAccess()
        except Exception:
            pass

    def _check_and_prompt_permissions(self):
        acc_ok = self._is_accessibility_trusted()
        inp_ok = self._is_input_monitoring_trusted()
        if acc_ok and inp_ok:
            return
        self._request_permissions_prompt()
        if not acc_ok and not inp_ok:
            self._set_status("Grant Accessibility + Input Monitoring, then relaunch")
        elif not acc_ok:
            self._set_status("Grant Accessibility permission, then relaunch")
        else:
            self._set_status("Grant Input Monitoring permission, then relaunch")

    # ====================================================================
    # Hotkey detection
    # ====================================================================
    def _key_identifier(self, key):
        if isinstance(key, keyboard.KeyCode):
            char = key.char.lower() if key.char else None
            return ("char", char)
        return ("key", key)

    def _is_fallback_combo_active(self) -> bool:
        ctrl = any(
            k in self._pressed_keys
            for k in [("key", keyboard.Key.ctrl), ("key", keyboard.Key.ctrl_l), ("key", keyboard.Key.ctrl_r)]
        )
        alt = any(
            k in self._pressed_keys
            for k in [("key", keyboard.Key.alt), ("key", keyboard.Key.alt_l), ("key", keyboard.Key.alt_r)]
        )
        d = ("char", "d") in self._pressed_keys
        return ctrl and alt and d

    def _on_key_press(self, key):
        self._pressed_keys.add(self._key_identifier(key))
        with self._lock:
            self._fallback_down = self._is_fallback_combo_active()
            self._update_ptt_state_locked()

    def _on_key_release(self, key):
        kid = self._key_identifier(key)
        self._pressed_keys.discard(kid)
        with self._lock:
            self._fallback_down = self._is_fallback_combo_active()
            self._update_ptt_state_locked()

    def _on_flags_changed(self, event):
        try:
            fn_down = bool(event.modifierFlags() & NSEventModifierFlagFunction)
        except Exception:
            return event
        with self._lock:
            if self._fn_down != fn_down:
                self._fn_down = fn_down
                self._update_ptt_state_locked()
        return event

    def _read_hid_fn_state(self) -> Optional[bool]:
        if any(v is None for v in [CGEventSourceFlagsState, kCGEventSourceStateHIDSystemState, kCGEventFlagMaskSecondaryFn]):
            return None
        try:
            flags = CGEventSourceFlagsState(kCGEventSourceStateHIDSystemState)
            return bool(flags & kCGEventFlagMaskSecondaryFn)
        except Exception:
            return None

    # ====================================================================
    # PTT state machine
    # ====================================================================
    def _update_ptt_state_locked(self):
        should_be_active = self._fn_down or self._fallback_down
        if should_be_active:
            self._start_ptt_if_needed()
        else:
            self._stop_ptt_if_needed()

    def _start_ptt_if_needed(self):
        if self._ptt_active:
            return
        self._ptt_active = True
        self._ptt_start_time = time.time()
        if not self._recording:
            self._start_recording_locked()

    def _stop_ptt_if_needed(self):
        if not self._ptt_active:
            return
        self._ptt_active = False
        self._ptt_start_time = None
        if self._recording:
            self._stop_recording_locked()

    def _start_ptt_watchdog(self):
        if self._ptt_watchdog_thread and self._ptt_watchdog_thread.is_alive():
            return
        self._ptt_watchdog_stop_event.clear()
        self._ptt_watchdog_thread = threading.Thread(
            target=self._ptt_watchdog_worker, daemon=True
        )
        self._ptt_watchdog_thread.start()

    def _stop_ptt_watchdog(self):
        self._ptt_watchdog_stop_event.set()

    def _ptt_watchdog_worker(self):
        while not self._ptt_watchdog_stop_event.wait(PTT_STATE_POLL_SEC):
            with self._lock:
                # Auto-stop if PTT held too long (prevents getting stuck)
                if self._ptt_active and self._ptt_start_time:
                    if time.time() - self._ptt_start_time > PTT_MAX_HOLD_SEC:
                        print(f"PTT timeout after {PTT_MAX_HOLD_SEC}s — force-stopping")
                        self._stop_ptt_if_needed()
                        continue
                if not self._fn_supported:
                    continue

            hid_fn_down = self._read_hid_fn_state()
            with self._lock:
                if hid_fn_down is None:
                    if self._fn_down and self._ptt_active:
                        self._fn_down = False
                        self._update_ptt_state_locked()
                    continue
                if self._fn_down != hid_fn_down:
                    self._fn_down = hid_fn_down
                    self._update_ptt_state_locked()

    # ====================================================================
    # Recording lifecycle
    # ====================================================================
    def _audio_callback(self, chunk: np.ndarray):
        """Called by AudioRecorder for each incoming audio chunk."""
        self._audio_chunks.append(chunk.reshape(-1, 1).copy())  # keep (N,1) shape for concatenation
        with self._audio_buffer_lock:
            self._fast_chunk_queue.append(chunk.copy())

    def _start_recording_locked(self):
        try:
            self._show_overlay()
            self._set_status("Recording")
            self.title = "R"

            self._audio_chunks = []
            with self._audio_buffer_lock:
                self._fast_chunk_queue = []

            self._audio_recorder = AudioRecorder(device_id=self._selected_input_device)
            self._audio_recorder.start(extra_callback=self._audio_callback)
            self._recording = True

            self._start_fast_commit_locked()
            self._start_live_preview_locked()
        except Exception as exc:
            self._recording = False
            self._audio_recorder = None
            self.title = "W"
            self._set_status(f"Mic error: {exc}")
            self._hide_overlay()

    def _stop_recording_locked(self):
        self._stop_fast_commit_locked()
        self._stop_live_preview_locked()

        raw_audio: Optional[np.ndarray] = None
        if self._audio_recorder is not None:
            raw_audio = self._audio_recorder.stop()
            self._audio_recorder = None

        self._recording = False
        self.title = "W"
        self._hide_overlay()

        if raw_audio is None or raw_audio.size == 0:
            if self._audio_chunks:
                raw_audio = np.concatenate(self._audio_chunks, axis=0).reshape(-1)
            self._audio_chunks = []

        if raw_audio is None or raw_audio.size == 0:
            self._set_status("No audio captured")
            return

        fast_segments = list(self._fast_chunk_text_segments)
        fast_processed = int(self._fast_processed_samples)
        fast_model = self._fast_commit_model_name or self._selected_model
        self._fast_chunk_text_segments = []
        self._fast_processed_samples = 0
        self._fast_commit_model_name = None

        self._set_status("Transcribing")
        threading.Thread(
            target=self._finalize_and_type,
            args=(raw_audio.copy(), self._selected_model, fast_model, fast_segments, fast_processed),
            daemon=True,
        ).start()

    def _toggle_recording(self):
        with self._lock:
            if not self._recording:
                self._start_recording_locked()
            else:
                self._stop_recording_locked()

    # ====================================================================
    # Live preview
    # ====================================================================
    def _snapshot_preview_audio_locked(self) -> Optional[np.ndarray]:
        if not self._audio_chunks:
            return None
        target = int(SAMPLE_RATE * LIVE_PREVIEW_WINDOW_SEC)
        min_samples = int(SAMPLE_RATE * LIVE_PREVIEW_MIN_AUDIO_SEC)
        collected = []
        total = 0
        for chunk in reversed(self._audio_chunks):
            flat = chunk.reshape(-1)
            collected.append(flat)
            total += flat.size
            if total >= target:
                break
        if total < min_samples:
            return None
        collected.reverse()
        snapshot = np.concatenate(collected)
        if snapshot.size > target:
            snapshot = snapshot[-target:]
        return snapshot.copy()

    def _start_live_preview_locked(self):
        if self._live_preview_thread and self._live_preview_thread.is_alive():
            return
        self._last_live_preview_text = ""
        self._live_preview_stop_event.clear()
        self._set_overlay_preview("Listening...")
        self._live_preview_thread = threading.Thread(
            target=self._live_preview_worker, daemon=True
        )
        self._live_preview_thread.start()

    def _stop_live_preview_locked(self):
        self._live_preview_stop_event.set()
        self._live_preview_thread = None
        self._last_live_preview_text = ""

    def _live_preview_worker(self):
        preview_model = get_preview_model_name(self._selected_model)
        while not self._live_preview_stop_event.wait(LIVE_PREVIEW_INTERVAL_SEC):
            with self._lock:
                if not self._recording:
                    continue
                audio_snapshot = self._snapshot_preview_audio_locked()
            if audio_snapshot is None:
                continue
            try:
                text = _transcribe_audio(
                    audio_snapshot,
                    model_name=preview_model,
                    language=self._selected_language_code,
                    is_preview=True,
                )
                preview = self._tail_words(text)
                if preview and preview != self._last_live_preview_text:
                    self._last_live_preview_text = preview
                    self._set_overlay_preview(preview)
            except Exception:
                continue

    # ====================================================================
    # Fast-commit (chunked transcription during long recordings)
    # ====================================================================
    def _drain_fast_queue(self) -> list[np.ndarray]:
        with self._audio_buffer_lock:
            if not self._fast_chunk_queue:
                return []
            queued = self._fast_chunk_queue
            self._fast_chunk_queue = []
            return queued

    def _start_fast_commit_locked(self):
        if self._fast_commit_thread and self._fast_commit_thread.is_alive():
            return
        self._fast_commit_model_name = self._selected_model
        self._fast_commit_stop_event.clear()
        self._fast_chunk_text_segments = []
        self._fast_processed_samples = 0
        with self._audio_buffer_lock:
            self._fast_chunk_queue = []
        self._fast_commit_thread = threading.Thread(
            target=self._fast_commit_worker, daemon=True
        )
        self._fast_commit_thread.start()

    def _stop_fast_commit_locked(self):
        self._fast_commit_stop_event.set()

    def _fast_commit_worker(self):
        chunk_samples = int(SAMPLE_RATE * FAST_COMMIT_CHUNK_SEC)
        buffer = np.zeros(0, dtype=np.float32)
        while not self._fast_commit_stop_event.wait(FAST_COMMIT_POLL_SEC):
            queued = self._drain_fast_queue()
            if queued:
                buffer = np.concatenate([buffer, *queued])
            while buffer.size >= chunk_samples:
                audio_chunk = buffer[:chunk_samples].copy()
                buffer = buffer[chunk_samples:]
                model_name = self._fast_commit_model_name or self._selected_model
                try:
                    text = _transcribe_audio(
                        audio_chunk,
                        model_name=model_name,
                        language=self._selected_language_code,
                        inference_lock=self._inference_lock,
                    )
                except Exception:
                    text = ""
                with self._lock:
                    self._fast_processed_samples += chunk_samples
                    if text:
                        self._fast_chunk_text_segments.append(text)

    # ====================================================================
    # Transcription & text injection
    # ====================================================================
    def _transcribe(self, audio: np.ndarray, model_name: str) -> str:
        """Transcribe audio using the shared transcription engine."""
        initial_prompt = as_prompt() or None
        return _transcribe_audio(
            normalize_audio(audio),
            model_name=model_name,
            language=self._selected_language_code,
            initial_prompt=initial_prompt,
            inference_lock=self._inference_lock,
        )

    def _finalize_and_type(
        self,
        audio: np.ndarray,
        model_name: str,
        fast_model_name: str,
        fast_segments: list[str],
        fast_processed_samples: int,
    ):
        raw_text = ""
        try:
            duration_sec = audio.size / SAMPLE_RATE if SAMPLE_RATE > 0 else 0

            # Short utterance: skip fast-commit path, use full model directly
            if duration_sec <= SHORT_UTTERANCE_FAST_PATH_SEC:
                raw_text = self._transcribe(audio, model_name)

            if fast_segments:
                raw_text = " ".join(seg for seg in fast_segments if seg).strip()
                safe_processed = min(max(fast_processed_samples, 0), audio.size)
                remaining = audio[safe_processed:]
                if remaining.size >= int(SAMPLE_RATE * FAST_COMMIT_MIN_TAIL_SEC):
                    tail = self._transcribe(remaining, model_name)
                    if tail:
                        raw_text = f"{raw_text} {tail}".strip()

            if not raw_text:
                raw_text = self._transcribe(audio, model_name)

            # LLM cleanup (optional, skipped for very short utterances)
            app_name = self._app_monitor.get()
            if self._llm_enabled and len(raw_text.split()) >= 3:
                cleaned_text, llm_ms = clean(raw_text, app_name)
                print(f"LLM cleanup: {llm_ms}ms")
            else:
                cleaned_text, llm_ms = raw_text, 0

            print(f"Raw:     {raw_text}")
            print(f"Cleaned: {cleaned_text}")

            formatted = format_transcript(cleaned_text)

            if not formatted or len(formatted.strip()) < 4:
                AppHelper.callAfter(self._set_status, "No speech recognized")
                return

            self._last_processed_text = formatted
            RUNTIME_LAST_TEXT_PATH.write_text(formatted, encoding="utf-8")
            AppHelper.callAfter(self._set_last_preview, formatted)

            app_name = self._app_monitor.get()
            success, reason = inject(formatted, app_name)

            if success:
                mode = "chunked" if fast_segments else "full"
                AppHelper.callAfter(self._set_status, f"Pasted ({model_name} / {mode})")
                rumps.notification("WhisperFlow", "Transcription inserted", formatted[:120])
            else:
                AppHelper.callAfter(self._show_injection_failure, formatted, reason)

            history_save(raw_text, formatted, app_name, llm_ms)

        except Exception as exc:
            self._set_status(f"Error: {exc}")

    def _show_injection_failure(self, text: str, reason: str):
        print(f"Injection failed: {reason}")
        try:
            _write_clipboard(text)
        except Exception as exc:
            print(f"Clipboard write failed: {exc}")
            return
        rumps.notification(
            "WhisperFlow",
            "Paste failed",
            f"Text copied to clipboard — press Cmd+V. ({reason})",
            sound=False,
        )
        self._set_status(f"Paste failed: {reason}")

    # ====================================================================
    # Menu callbacks
    # ====================================================================
    def _on_models_ready(self):
        self.title = "W"
        rumps.notification("WhisperFlow", "", "Models ready", sound=False)

    def _on_open_home(self, _):
        webbrowser.open(HOME_URL)

    def _on_check_updates(self, _):
        webbrowser.open(UPDATES_URL)

    def _on_open_help(self, _):
        webbrowser.open(HELP_CENTER_URL)

    def _on_open_feedback(self, _):
        webbrowser.open(FEEDBACK_URL)

    def _on_open_permissions(self, _):
        webbrowser.open("x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility")
        webbrowser.open("x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent")

    def _on_test_overlay(self, _):
        self._show_overlay()
        threading.Timer(2.0, self._hide_overlay).start()

    def _on_copy_last(self, _):
        if not self._last_processed_text:
            self._set_status("No transcript to copy")
            return
        try:
            subprocess.run(["pbcopy"], input=self._last_processed_text.encode(), check=True)
            self._set_status("Copied last transcript")
        except Exception as exc:
            self._set_status(f"Copy failed: {exc}")

    def _on_paste_last(self, _):
        if not self._last_processed_text:
            self._set_status("No transcript to paste")
            return
        try:
            subprocess.run(["pbcopy"], input=self._last_processed_text.encode(), check=True)
            time.sleep(0.05)
            with self._keyboard.pressed(keyboard.Key.cmd):
                self._keyboard.press("v")
                self._keyboard.release("v")
            self._set_status("Pasted last transcript")
        except Exception as exc:
            self._set_status(f"Paste failed: {exc}")

    def _on_toggle_llm(self, _):
        self._llm_enabled = not self._llm_enabled
        label = "LLM Cleanup: ON" if self._llm_enabled else "LLM Cleanup: OFF"
        self._llm_toggle_item.title = label
        settings_set("llm_enabled", self._llm_enabled)
        self._set_status(label)

    def _on_select_microphone(self, sender):
        entry = self._mic_items.get(sender.title)
        if entry is None:
            return
        device_id, _ = entry
        self._selected_input_device = device_id
        for _, item in self._mic_items.values():
            item.state = 0
        sender.state = 1
        settings_set("device_id", device_id)
        self._set_status(f"Microphone: {sender.title}")

    def _on_select_language(self, sender):
        label = sender.title
        if label not in SUPPORTED_LANGUAGES:
            return
        self._selected_language_label = label
        self._selected_language_code = SUPPORTED_LANGUAGES[label]
        for lbl, item in self._language_items.items():
            item.state = int(lbl == label)
        settings_set("language", self._selected_language_code)
        settings_set("language_label", label)
        self._set_status(f"Language: {label}")

    def _on_select_model(self, sender):
        self._selected_model = sender.title
        for name, item in self._model_items.items():
            item.state = int(name == sender.title)
        settings_set("model", sender.title)
        self._set_status(f"Model: {sender.title}")

    def _on_show_dictionary(self, _):
        words = dict_load()
        current = ", ".join(words) if words else "Empty"
        response = rumps.Window(
            message=f"Current words: {current}\n\nAdd a word:",
            title="Personal Dictionary",
            default_text="",
            ok="Add",
            cancel="Close",
        ).run()
        if response.clicked and response.text.strip():
            dict_add(response.text.strip())
            rumps.notification("Dictionary", "", f"Added: {response.text.strip()}")

    def _on_show_history(self, _):
        entries = history_load()
        if not entries:
            rumps.alert("No history yet.")
            return
        lines = []
        for e in entries:
            date = e.get("timestamp", "").split("T")[0]
            app = e.get("app", "unknown")
            text = e.get("cleaned", "")[:60]
            lines.append(f"[{date}][{app}] {text}...")
        rumps.alert("Recent Dictations", message="\n".join(lines))

    def _on_quit(self, _):
        with self._lock:
            self._stop_fast_commit_locked()
            self._stop_live_preview_locked()
            if self._recording:
                self._stop_recording_locked()
            self._ptt_active = False
            self._fn_down = False
            self._fallback_down = False
        self._stop_ptt_watchdog()
        self._hide_overlay()
        self._hotkey_listener.stop()
        self._app_monitor.stop()
        rumps.quit_application()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    app = WhisperMenuBarApp()
    if RUNTIME_LAST_TEXT_PATH.exists():
        try:
            app._last_processed_text = RUNTIME_LAST_TEXT_PATH.read_text(encoding="utf-8").strip()
            app._set_last_preview(app._last_processed_text)
        except Exception:
            pass
    app.run()


if __name__ == "__main__":
    main()
