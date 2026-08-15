"""
RoastMyAudio — macOS Menu Bar App.

Hold Fn (or Ctrl+Option+D) for Push-to-Talk, or use Hands-Free Toggle Mode.
Features live sound-reactive waveform HUD, smart app + clipboard context injection,
voice editing commands ("scratch that"), and embedded local LLM cleanup.
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
        NSNotificationCenter,
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
    from config import FLASK_HOST, FLASK_PORT, SUPPORTED_LLM_MODELS
    from src.apps.macos.audio_recorder import (
        SAMPLE_RATE,
        AudioRecorder,
        get_default_input_device,
        list_input_devices,
        normalize_audio,
    )
    from src.apps.macos.hud_overlay import DictationOverlay, _normalize_audio_level
    from src.apps.macos.warmup import load_models_async
    from src.shared.context_detector import (
        build_whisper_prompt,
        get_app_mode,
    )
    from src.shared.dictionary import add as dict_add
    from src.shared.dictionary import as_prompt
    from src.shared.dictionary import load as dict_load
    from src.shared.formatter import format_transcript, format_transcript_strict
    from src.shared.history import load as history_load
    from src.shared.history import save_recording as history_save_recording
    from src.shared.llm_cleanup import clean, cleanup_llm
    from src.shared.settings import load as settings_load
    from src.shared.settings import set as settings_set
    from src.shared.text_injector import AppMonitor, _save_clipboard, _write_clipboard, inject
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

HOME_URL = "https://github.com/roastmyaudio/roastmyaudio"
UPDATES_URL = "https://github.com/roastmyaudio/roastmyaudio/releases"
HELP_CENTER_URL = "https://github.com/roastmyaudio/roastmyaudio#readme"
SUPPORT_URL = "https://github.com/roastmyaudio/roastmyaudio/discussions"
FEEDBACK_URL = "https://github.com/roastmyaudio/roastmyaudio/issues"

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
        super().__init__("🎙️")

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
        self._selected_model: str = _settings.get("model", "base")
        self._selected_language_label: str = _settings.get("language_label", "English")
        self._selected_language_code: Optional[str] = _settings.get("language", "en")
        self._llm_enabled: bool = _settings.get("llm_enabled", True)
        self._llm_model: str = _settings.get("llm_model", "qwen2.5-0.5b")
        self._dictation_mode: str = _settings.get("dictation_mode", "push_to_talk")
        self._context_awareness: bool = _settings.get("context_awareness", True)
        self._voice_commands: bool = _settings.get("voice_commands", True)

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

        self._dashboard_item = rumps.MenuItem("Open Flow Dashboard", callback=self._on_open_dashboard)
        self._home_item = rumps.MenuItem("Home", callback=self._on_open_home)
        self._updates_item = rumps.MenuItem("Check for updates...", callback=self._on_check_updates)

        self._paste_last_item = rumps.MenuItem("Paste last transcript", callback=self._on_paste_last)
        self._last_preview_item = rumps.MenuItem("No transcript yet")
        self._last_preview_item.set_callback(None)

        self._permissions_item = rumps.MenuItem("Open macOS Permissions", callback=self._on_open_permissions)
        self._dictionary_item = rumps.MenuItem("Personal Dictionary", callback=self._on_show_dictionary)
        self._history_item = rumps.MenuItem("Recent Dictations", callback=self._on_show_history)

        self._hotkey_hint_item = rumps.MenuItem(self._get_hotkey_hint())
        self._hotkey_hint_item.set_callback(None)

        self._copy_last_item = rumps.MenuItem("Copy Last Processed", callback=self._on_copy_last)
        self._test_overlay_item = rumps.MenuItem("Test Overlay (2s)", callback=self._on_test_overlay)

        # Dictation Mode Submenu (Push-to-Talk vs Hands-Free Toggle)
        self._mode_menu = rumps.MenuItem("Dictation Mode")
        self._mode_ptt_item = rumps.MenuItem("Push-to-Talk (Hold Key)", callback=self._on_select_mode_ptt)
        self._mode_ptt_item.state = int(self._dictation_mode == "push_to_talk")
        self._mode_hands_free_item = rumps.MenuItem("Hands-Free Toggle (Tap Key)", callback=self._on_select_mode_hands_free)
        self._mode_hands_free_item.state = int(self._dictation_mode == "hands_free")
        self._mode_menu.add(self._mode_ptt_item)
        self._mode_menu.add(self._mode_hands_free_item)

        # Smart Context & Voice Commands Toggles
        self._context_toggle_item = rumps.MenuItem("Smart Context Injection", callback=self._on_toggle_context)
        self._context_toggle_item.state = int(self._context_awareness)

        self._voice_cmd_toggle_item = rumps.MenuItem("Voice Editing Commands", callback=self._on_toggle_voice_commands)
        self._voice_cmd_toggle_item.state = int(self._voice_commands)

        # AI Cleanup submenu (Metal GPU accelerated)
        self._llm_menu = rumps.MenuItem("AI Cleanup (Metal)")
        self._llm_toggle_item = rumps.MenuItem("Enable AI Cleanup", callback=self._on_toggle_llm)
        self._llm_toggle_item.state = int(self._llm_enabled)
        self._llm_menu.add(self._llm_toggle_item)
        self._llm_menu.add(None)

        self._llm_model_items: dict[str, rumps.MenuItem] = {}
        for key, info in SUPPORTED_LLM_MODELS.items():
            item = rumps.MenuItem(info["display_name"], callback=self._on_select_llm_model)
            item.state = int(key == self._llm_model)
            self._llm_menu.add(item)
            self._llm_model_items[key] = item

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
        self._quit_item = rumps.MenuItem("Quit RoastMyAudio", callback=self._on_quit)

        self.menu = [
            self._dashboard_item,
            self._home_item,
            self._updates_item,
            None,
            self._paste_last_item,
            self._last_preview_item,
            None,
            self._hotkey_hint_item,
            self._mode_menu,
            self._context_toggle_item,
            self._voice_cmd_toggle_item,
            None,
            self._mic_menu,
            self._language_menu,
            self._model_menu,
            self._llm_menu,
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
        self._start_dashboard_server()

        # Background warmup
        load_models_async(on_complete=self._on_models_ready)

    def _start_dashboard_server(self):
        """Start embedded Flow Dashboard Flask server in background daemon thread."""
        def _run():
            try:
                import logging
                logging.getLogger("werkzeug").setLevel(logging.ERROR)
                from src.apps.web.app import app as web_app
                web_app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, use_reloader=False)
            except Exception as exc:
                print(f"Dashboard background server notice: {exc}")

        t = threading.Thread(target=_run, daemon=True, name="FlowDashboardServer")
        t.start()

    def _get_hotkey_hint(self) -> str:
        if self._dictation_mode == "hands_free":
            return "Hands-Free: tap Fn (or Ctrl+Opt+D) to start/stop"
        return "Push-to-talk: hold Fn (or Ctrl+Opt+D)"

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
        app_name = self._app_monitor.get()
        mode = get_app_mode(app_name).capitalize() if self._context_awareness else ""
        if self._dictation_mode == "hands_free":
            badge = f"Hands-Free · {mode}" if mode else "Hands-Free"
        else:
            badge = mode or "PTT"

        def _do_show():
            self._overlay.show()
            self._overlay.set_title(f"Dictating · {self._selected_model}", badge)

        AppHelper.callAfter(_do_show)

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
            prev_fallback = self._fallback_down
            self._fallback_down = self._is_fallback_combo_active()
            if self._dictation_mode == "hands_free":
                if self._fallback_down and not prev_fallback:
                    self._toggle_recording_locked()
            else:
                self._update_ptt_state_locked()

    def _on_key_release(self, key):
        self._pressed_keys.discard(self._key_identifier(key))
        with self._lock:
            self._fallback_down = self._is_fallback_combo_active()
            if self._dictation_mode == "push_to_talk":
                self._update_ptt_state_locked()

    def _on_flags_changed(self, event):
        if not self._fn_supported:
            return event
        flags = int(event.modifierFlags())
        fn_down = bool(flags & NSEventModifierFlagFunction)
        with self._lock:
            if self._dictation_mode == "hands_free":
                if fn_down and not self._fn_down:
                    self._toggle_recording_locked()
                self._fn_down = fn_down
            else:
                if self._fn_down != fn_down:
                    self._fn_down = fn_down
                    self._update_ptt_state_locked()
        return event

    def _read_hid_fn_state(self) -> Optional[bool]:
        if (
            not self._fn_supported
            or CGEventSourceFlagsState is None
            or kCGEventSourceStateHIDSystemState is None
            or kCGEventFlagMaskSecondaryFn is None
        ):
            return None
        try:
            flags = CGEventSourceFlagsState(kCGEventSourceStateHIDSystemState)
            return bool(flags & kCGEventFlagMaskSecondaryFn)
        except Exception:
            return None

    def _update_ptt_state_locked(self):
        should_be_active = self._fn_down or self._fallback_down
        if should_be_active == self._ptt_active:
            return
        self._ptt_active = should_be_active
        if self._ptt_active:
            self._ptt_start_time = time.time()
            if not self._recording:
                self._start_recording_locked()
        else:
            self._ptt_start_time = None
            if self._recording:
                self._stop_recording_locked()

    def _toggle_recording_locked(self):
        if not self._recording:
            self._start_recording_locked()
        else:
            self._stop_recording_locked()

    def _stop_ptt_if_needed(self):
        if not self._ptt_active and not self._recording:
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
                if self._dictation_mode == "hands_free":
                    continue
                if self._ptt_active and self._ptt_start_time:
                    if time.time() - self._ptt_start_time > PTT_MAX_HOLD_SEC:
                        print(f"PTT timeout after {PTT_MAX_HOLD_SEC}s — force-stopping")
                        self._stop_ptt_if_needed()
                        continue

    # ====================================================================
    # Recording lifecycle
    # ====================================================================
    def _audio_callback(self, chunk: np.ndarray):
        """Called by AudioRecorder for each incoming audio chunk."""
        self._audio_chunks.append(chunk.reshape(-1, 1).copy())
        with self._audio_buffer_lock:
            self._fast_chunk_queue.append(chunk.copy())
        if self._overlay is not None and chunk.size and self._recording:
            flat = chunk.reshape(-1)
            rms = float(np.sqrt(np.mean(flat * flat)))
            AppHelper.callAfter(self._overlay.set_audio_level, _normalize_audio_level(rms))

    def _start_recording_locked(self):
        try:
            self._show_overlay()
            self._set_status("Recording")
            self.title = "🔴"

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
            self.title = "🎙️"
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
        self.title = "🎙️"
        self._hide_overlay()

        if raw_audio is None or raw_audio.size == 0:
            if self._audio_chunks:
                raw_audio = np.concatenate(self._audio_chunks, axis=0).reshape(-1)
            self._audio_chunks = []

        if raw_audio is None or raw_audio.size < int(SAMPLE_RATE * 0.25):
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
        """Transcribe audio with optional smart context injection."""
        app_name = self._app_monitor.get()
        if self._context_awareness:
            clipboard_text = _save_clipboard()
            custom_words = dict_load()
            initial_prompt = build_whisper_prompt(
                app_name=app_name,
                clipboard_text=clipboard_text,
                custom_words=custom_words,
            ) or None
        else:
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
        cleaned_text = ""
        formatted = ""
        llm_ms = 0
        app_name = self._app_monitor.get()
        duration_sec = audio.size / SAMPLE_RATE if SAMPLE_RATE > 0 else 0

        try:
            # Full-context transcription on complete audio array
            raw_text = self._transcribe(audio, model_name)

            # LLM cleanup (context conditioned)
            if self._llm_enabled and raw_text and len(raw_text.split()) >= 2:
                cleaned_text, llm_ms = clean(raw_text, app_name, model_key=self._llm_model)
                print(f"LLM cleanup ({self._llm_model}): {llm_ms}ms")
            else:
                cleaned_text, llm_ms = raw_text, 0

            print(f"Raw:     {raw_text}")
            print(f"Cleaned: {cleaned_text}")

            if self._voice_commands:
                formatted = format_transcript(cleaned_text)
            else:
                formatted = format_transcript_strict(cleaned_text)

            # Always save audio recording into dashboard history
            history_save_recording(
                audio=audio,
                raw=raw_text,
                cleaned=cleaned_text,
                formatted=formatted or raw_text,
                app=app_name,
                latency_ms=llm_ms,
                model_used=model_name,
                llm_model=self._llm_model,
                duration_sec=duration_sec,
                status="completed" if (formatted and len(formatted.strip()) >= 2) else "failed",
            )

            if not formatted or len(formatted.strip()) < 2:
                AppHelper.callAfter(self._set_status, "No speech recognized")
                return

            self._last_processed_text = formatted
            RUNTIME_LAST_TEXT_PATH.write_text(formatted, encoding="utf-8")
            AppHelper.callAfter(self._set_last_preview, formatted)

            success, reason = inject(formatted, app_name)

            if success:
                AppHelper.callAfter(self._set_status, f"Pasted ({model_name})")
                rumps.notification("RoastMyAudio", "Transcription inserted", formatted[:120])
            else:
                AppHelper.callAfter(self._show_injection_failure, formatted, reason)

        except Exception as exc:
            print(f"Finalize error: {exc}")
            self._set_status(f"Error: {exc}")
            # Fallback save on error
            try:
                history_save_recording(
                    audio=audio,
                    raw=raw_text,
                    cleaned=cleaned_text,
                    formatted=formatted or raw_text or str(exc),
                    app=app_name,
                    latency_ms=llm_ms,
                    model_used=model_name,
                    llm_model=self._llm_model,
                    duration_sec=duration_sec,
                    status="failed",
                )
            except Exception:
                pass

    def _show_injection_failure(self, text: str, reason: str):
        print(f"Injection failed: {reason}")
        try:
            _write_clipboard(text)
        except Exception as exc:
            print(f"Clipboard write failed: {exc}")
            return
        rumps.notification(
            "RoastMyAudio",
            "Paste failed",
            f"Text copied to clipboard — press Cmd+V. ({reason})",
            sound=False,
        )
        self._set_status(f"Paste failed: {reason}")

    # ====================================================================
    # Menu callbacks
    # ====================================================================
    def _on_models_ready(self):
        self.title = "🎙️"
        rumps.notification("RoastMyAudio", "", "Models ready", sound=False)

    def _on_open_dashboard(self, _):
        webbrowser.open(f"http://{FLASK_HOST}:{FLASK_PORT}")

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
        AppHelper.callAfter(self._overlay.set_preview_text, "Testing 14-bar crazy wave HUD...")
        AppHelper.callAfter(self._overlay.set_audio_level, 0.85)
        threading.Timer(3.0, self._hide_overlay).start()

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

    def _on_select_mode_ptt(self, _):
        self._dictation_mode = "push_to_talk"
        self._mode_ptt_item.state = 1
        self._mode_hands_free_item.state = 0
        settings_set("dictation_mode", "push_to_talk")
        self._hotkey_hint_item.title = self._get_hotkey_hint()
        self._set_status("Mode: Push-to-Talk")

    def _on_select_mode_hands_free(self, _):
        self._dictation_mode = "hands_free"
        self._mode_ptt_item.state = 0
        self._mode_hands_free_item.state = 1
        settings_set("dictation_mode", "hands_free")
        self._hotkey_hint_item.title = self._get_hotkey_hint()
        self._set_status("Mode: Hands-Free Toggle")

    def _on_toggle_context(self, sender):
        self._context_awareness = not self._context_awareness
        sender.state = int(self._context_awareness)
        settings_set("context_awareness", self._context_awareness)
        self._set_status(f"Smart Context: {'ON' if self._context_awareness else 'OFF'}")

    def _on_toggle_voice_commands(self, sender):
        self._voice_commands = not self._voice_commands
        sender.state = int(self._voice_commands)
        settings_set("voice_commands", self._voice_commands)
        self._set_status(f"Voice Commands: {'ON' if self._voice_commands else 'OFF'}")

    def _on_toggle_llm(self, sender):
        self._llm_enabled = not self._llm_enabled
        sender.state = int(self._llm_enabled)
        settings_set("llm_enabled", self._llm_enabled)
        self._set_status(f"AI Cleanup: {'ON' if self._llm_enabled else 'OFF'}")

    def _on_select_llm_model(self, sender):
        selected_key = None
        for key, item in self._llm_model_items.items():
            if item.title == sender.title:
                selected_key = key
                item.state = 1
            else:
                item.state = 0
        if selected_key:
            self._llm_model = selected_key
            settings_set("llm_model", selected_key)
            self._set_status(f"AI Model: {SUPPORTED_LLM_MODELS[selected_key]['display_name']}")

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
        cleanup_llm()
        rumps.quit_application()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    import signal

    def _cleanup_and_exit(sig=None, frame=None):
        cleanup_llm()
        os._exit(0)

    try:
        signal.signal(signal.SIGINT, _cleanup_and_exit)
        signal.signal(signal.SIGTERM, _cleanup_and_exit)
    except Exception:
        pass

    if APPKIT_AVAILABLE:
        try:
            NSNotificationCenter.defaultCenter().addObserverForName_object_queue_usingBlock_(
                "NSApplicationWillTerminateNotification",
                None,
                None,
                lambda notif: cleanup_llm(),
            )
        except Exception:
            pass

    app = WhisperMenuBarApp()
    if RUNTIME_LAST_TEXT_PATH.exists():
        try:
            app._last_processed_text = RUNTIME_LAST_TEXT_PATH.read_text(encoding="utf-8").strip()
            app._set_last_preview(app._last_processed_text)
        except Exception:
            pass
    try:
        app.run()
    finally:
        cleanup_llm()


if __name__ == "__main__":
    main()
