import sys
import subprocess
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional

import numpy as np
import rumps
import sounddevice as sd
from pynput import keyboard
import torch
import logging

# Silence noisy external libraries
import warnings
warnings.filterwarnings("ignore", message=".*upgraded your loaded checkpoint.*")
logging.getLogger("openai").setLevel(logging.ERROR)

try:
    from AppKit import (
        NSApp,
        NSBackingStoreBuffered,
        NSColor,
        NSEvent,
        NSEventMaskFlagsChanged,
        NSEventModifierFlagFunction,
        NSMouseInRect,
        NSScreen,
        NSScreenSaverWindowLevel,
        NSWindow,
        NSWindowCollectionBehaviorCanJoinAllSpaces,
        NSWindowCollectionBehaviorFullScreenAuxiliary,
        NSWindowCollectionBehaviorMoveToActiveSpace,
        NSWindowCollectionBehaviorStationary,
        NSWindowStyleMaskBorderless,
        NSProgressIndicator,
        NSProgressIndicatorStyleSpinning,
        NSTextField,
    )
    from Foundation import NSMakeRect
    from PyObjCTools import AppHelper

    APPKIT_AVAILABLE = True
except Exception:  # noqa: BLE001
    APPKIT_AVAILABLE = False

try:
    from ApplicationServices import AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt
except Exception:  # noqa: BLE001
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
except Exception:  # noqa: BLE001
    CGEventSourceFlagsState = None
    CGPreflightListenEventAccess = None
    CGRequestListenEventAccess = None
    kCGEventFlagMaskSecondaryFn = None
    kCGEventSourceStateHIDSystemState = None

# --- PATH SETUP ---
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import os

# Suppress annoying Objective-C duplicated class warnings from PyAV vs Homebrew FFmpeg
old_stderr = os.dup(2)
devnull = os.open(os.devnull, os.O_WRONLY)
os.dup2(devnull, 2)
try:
    from src.web_ui.app import format_transcript, get_default_model_name, get_installed_models, get_model_by_name
    from llm_cleanup import clean, warmup
    from text_injector import AppMonitor, inject, _write_clipboard
    from warmup import load_models_async
    from dictionary import load as dict_load, add as dict_add, as_prompt
    from history import save as history_save, load as history_load
finally:
    os.dup2(old_stderr, 2)
    os.close(devnull)
    os.close(old_stderr)


# Load Silero VAD model once at startup
try:
    VAD_MODEL, VAD_UTILS = torch.hub.load(
        repo_or_dir='snakers4/silero-vad',
        model='silero_vad',
        force_reload=False
    )
    (GET_SPEECH_TIMESTAMPS, _, READ_AUDIO, *_) = VAD_UTILS
    VAD_AVAILABLE = True
except Exception:  # noqa: BLE001
    VAD_MODEL = None
    VAD_UTILS = None
    GET_SPEECH_TIMESTAMPS = None
    READ_AUDIO = None
    VAD_AVAILABLE = False

SAMPLE_RATE = 16000
CHANNELS = 1
FALLBACK_HOLD_HOTKEY = "Ctrl+Option+D"
LIVE_PREVIEW_INTERVAL_SEC = 0.6
LIVE_PREVIEW_WINDOW_SEC = 2.0
LIVE_PREVIEW_MIN_AUDIO_SEC = 0.45
LIVE_PREVIEW_WORD_LIMIT = 6
LIVE_PREVIEW_MODEL_PREFERENCE = ("tiny.en", "tiny", "base.en", "base")
PTT_STATE_POLL_SEC = 0.12
PTT_MAX_HOLD_SEC = 300  # Auto-stop after 5 minutes if stuck
FAST_COMMIT_CHUNK_SEC = 1.0
FAST_COMMIT_POLL_SEC = 0.1
FAST_COMMIT_MIN_TAIL_SEC = 0.1
SHORT_UTTERANCE_FAST_PATH_SEC = 0.8
AUDIO_NORM_TARGET_RMS = 0.15
RUNTIME_DIR = Path(__file__).resolve().parent / "runtime"
RUNTIME_LAST_TEXT_PATH = RUNTIME_DIR / "last_processed.txt"

HOME_URL = "https://github.com/openai/whisper"
UPDATES_URL = "https://github.com/openai/whisper/releases"
HELP_CENTER_URL = "https://github.com/openai/whisper#readme"
SUPPORT_URL = "https://github.com/openai/whisper/discussions"
FEEDBACK_URL = "https://github.com/openai/whisper/issues"

SUPPORTED_LANGUAGES = {
    "English": "en",
}


def get_active_app_name() -> str:
    if not APPKIT_AVAILABLE:
        return ""
    try:
        from AppKit import NSWorkspace
        workspace = NSWorkspace.sharedWorkspace()
        active_app = workspace.activeApplication()
        if active_app:
            bundle_id = active_app.get('NSApplicationBundleIdentifier', '')
            process_name = active_app.get('NSApplicationName', '')
            return bundle_id or process_name or ""
        return ""
    except Exception:  # noqa: BLE001
        return ""


def trim_silence(audio: np.ndarray) -> Optional[np.ndarray]:
    if not VAD_AVAILABLE or audio.size == 0:
        return audio
    try:
        if isinstance(audio, np.ndarray):
            wav_tensor = torch.from_numpy(audio).float()
        else:
            wav_tensor = audio
        timestamps = GET_SPEECH_TIMESTAMPS(wav_tensor, VAD_MODEL, sampling_rate=SAMPLE_RATE, threshold=0.8)
        if not timestamps:
            return None
        start = timestamps[0]['start']
        end = timestamps[-1]['end']
        return wav_tensor[start:end].numpy()
    except Exception:  # noqa: BLE001
        return audio


def transcribe_with_timing(
    audio: np.ndarray,
    model_name: str = "base",
    language: Optional[str] = "en",
    normalize_audio: bool = True,
) -> dict:
    t0 = time.time()
    trimmed = trim_silence(audio)
    t1 = time.time()
    vad_ms = (t1 - t0) * 1000
    if trimmed is None:
        return {
            'vad_ms': vad_ms,
            'asr_ms': 0,
            'pcl_ms': 0,
            'total_ms': (time.time() - t0) * 1000,
            'raw_text': "",
            'cleaned_text': "",
            'had_speech': False,
        }
    if isinstance(trimmed, torch.Tensor):
        trimmed = trimmed.numpy()
    if normalize_audio:
        trimmed = _normalize_audio_for_quiet_speech_static(trimmed)
    t1_5 = time.time()
    try:
        raw_text = WhisperMenuBarApp._safe_transcribe_static(
            model_name, trimmed, language=language or "en", initial_prompt=None
        )
        t2 = time.time()
        asr_ms = (t2 - t1_5) * 1000
    except Exception as e:  # noqa: BLE001
        return {
            'vad_ms': vad_ms, 'asr_ms': 0, 'pcl_ms': 0, 'total_ms': (time.time() - t0) * 1000,
            'raw_text': "", 'cleaned_text': "", 'had_speech': True, 'error': str(e)
        }
    t2_5 = time.time()
    llm_cleaned_text, llm_ms = clean(raw_text, model_name)
    cleaned_text = format_transcript(llm_cleaned_text)
    t3 = time.time()
    pcl_ms = (t3 - t2_5) * 1000
    return {
        'vad_ms': vad_ms, 'asr_ms': asr_ms, 'pcl_ms': pcl_ms, 'total_ms': (t3 - t0) * 1000,
        'raw_text': raw_text, 'cleaned_text': cleaned_text, 'had_speech': True,
    }


def _normalize_audio_for_quiet_speech_static(audio: np.ndarray) -> np.ndarray:
    if audio.size == 0: return audio
    rms = np.sqrt(np.mean(audio**2))
    if rms < 0.001: return audio
    scale = min(AUDIO_NORM_TARGET_RMS / rms, 3.0)
    return np.clip(audio * scale, -1.0, 1.0)


def _filter_hallucinations(text: str) -> str:
    if not text or len(text.strip()) < 3: return text
    words = text.split()
    total_words = len(words)
    word_counts = {}
    for word in words:
        normalized = word.lower().rstrip('.,!?;:')
        word_counts[normalized] = word_counts.get(normalized, 0) + 1
    if word_counts:
        most_common_word = max(word_counts, key=word_counts.get)
        if word_counts[most_common_word] / total_words > 0.1:
            filtered_words = [w for w in words if w.lower().rstrip('.,!?;:') != most_common_word]
            return _filter_hallucinations(" ".join(filtered_words)) if filtered_words else ""
    hallucination_indicators = {'you', 'i', 'uh', 'um', 'ah', 'so', 'ok', 'thank', 'well', 'like', 'just'}
    hallucin_count = sum(1 for word in words if word.lower().rstrip('.,!?;:') in hallucination_indicators)
    if hallucin_count / total_words > 0.3:
        real_words = [w for w in words if w.lower().rstrip('.,!?;:') not in hallucination_indicators]
        return " ".join(real_words) if len(real_words) >= 3 else ""
    return text.strip()


class _DictationOverlay:
    def __init__(self):
        self.window = None
        self.title_label = None
        self.preview_label = None
        self.hint_label = None
        self.spinner = None
        self.pill_width = 420
        self.pill_height = 112
        self.bottom_margin = 72
        self._build_window()

    def _make_label(self, text: str, frame):
        label = NSTextField.alloc().initWithFrame_(frame)
        label.setStringValue_(text)
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setEditable_(False)
        label.setSelectable_(False)
        label.setAlignment_(1)
        label.setTextColor_(NSColor.whiteColor())
        label.setFont_(None)
        return label

    def _pill_frame_for_screen(self, screen_frame):
        x = screen_frame.origin.x + (screen_frame.size.width - self.pill_width) / 2
        y = screen_frame.origin.y + self.bottom_margin
        return NSMakeRect(x, y, self.pill_width, self.pill_height)

    def _screen_for_current_pointer(self):
        mouse_point = NSEvent.mouseLocation()
        for screen in NSScreen.screens():
            if NSMouseInRect(mouse_point, screen.frame(), False): return screen
        return NSScreen.mainScreen()

    def _layout_content(self):
        width, height = self.pill_width, self.pill_height
        self.title_label.setFrame_(NSMakeRect(58, height - 34, width - 70, 20))
        self.preview_label.setFrame_(NSMakeRect(58, 40, width - 70, 26))
        self.hint_label.setFrame_(NSMakeRect(58, 14, width - 70, 18))
        self.spinner.setFrame_(NSMakeRect(20, (height - 20) / 2, 20, 20))

    def _build_window(self):
        screen = NSScreen.mainScreen()
        frame = self._pill_frame_for_screen(screen.frame())
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            frame, NSWindowStyleMaskBorderless, NSBackingStoreBuffered, False
        )
        self.window.setReleasedWhenClosed_(False)
        self.window.setOpaque_(False)
        self.window.setBackgroundColor_(NSColor.colorWithCalibratedRed_green_blue_alpha_(0.06, 0.06, 0.08, 0.86))
        self.window.setIgnoresMouseEvents_(True)
        self.window.setLevel_(NSScreenSaverWindowLevel)
        self.window.setHasShadow_(True)
        self.window.setCollectionBehavior_(NSWindowCollectionBehaviorFullScreenAuxiliary | NSWindowCollectionBehaviorMoveToActiveSpace)
        content_view = self.window.contentView()
        content_view.setWantsLayer_(True)
        content_view.layer().setCornerRadius_(self.pill_height / 2)
        content_view.layer().setMasksToBounds_(True)
        self.title_label = self._make_label("Dictating with Whisper", NSMakeRect(0, 0, 300, 22))
        self.preview_label = self._make_label("Listening...", NSMakeRect(0, 0, 300, 26))
        self.preview_label.setTextColor_(NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.95))
        self.hint_label = self._make_label("Release key to transcribe and paste", NSMakeRect(0, 0, 300, 18))
        self.hint_label.setTextColor_(NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.82))
        self.spinner = NSProgressIndicator.alloc().initWithFrame_(NSMakeRect(0, 0, 20, 20))
        self.spinner.setStyle_(NSProgressIndicatorStyleSpinning)
        self.spinner.setIndeterminate_(True)
        self.spinner.setDisplayedWhenStopped_(False)
        content_view.addSubview_(self.title_label)
        content_view.addSubview_(self.preview_label)
        content_view.addSubview_(self.hint_label)
        content_view.addSubview_(self.spinner)
        self._layout_content()
        self.window.orderOut_(None)

    def show(self):
        screen = self._screen_for_current_pointer()
        frame = self._pill_frame_for_screen(screen.frame())
        self.window.setFrame_display_(frame, True)
        self._layout_content()
        self.preview_label.setStringValue_("Listening...")
        self.spinner.startAnimation_(None)
        self.window.orderFrontRegardless()

    def hide(self):
        self.spinner.stopAnimation_(None)
        self.window.orderOut_(None)

    def set_preview_text(self, text: str):
        if self.preview_label:
            self.preview_label.setStringValue_((text or "").strip() or "Listening...")


class WhisperMenuBarApp(rumps.App):
    def __init__(self):
        super().__init__("W")
        self._lock = threading.Lock()
        self._recording = False
        self._audio_chunks = []
        self._stream = None
        self._pressed_keys = set()
        self._ptt_active = False
        self._fn_down = False
        self._fallback_down = False
        self._last_processed_text = ""
        self._fn_supported = APPKIT_AVAILABLE
        self._overlay = _DictationOverlay() if APPKIT_AVAILABLE else None
        self._ptt_watchdog_thread = None
        self._ptt_watchdog_stop_event = threading.Event()
        self._ptt_start_time = None
        self._live_preview_thread = None
        self._live_preview_stop_event = threading.Event()
        self._inference_lock = threading.Lock()
        self._audio_buffer_lock = threading.Lock()
        self._live_preview_model_name = None
        self._last_live_preview_text = ""
        self._fast_commit_thread = None
        self._fast_commit_stop_event = threading.Event()
        self._fast_chunk_queue = []
        self._fast_chunk_text_segments = []
        self._fast_processed_samples = 0
        self._fast_commit_model_name = None
        self._selected_language_label = "English"
        self._selected_language_code = "en"
        self._selected_input_device = self._find_default_input_device()
        self._app_monitor = AppMonitor()
        installed_models = get_installed_models()
        self._selected_model = "turbo"
        self._keyboard = keyboard.Controller()
        self._model_items = {}
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        self._status_item = rumps.MenuItem("Status: Idle")
        self._status_item.set_callback(None)
        self._home_item = rumps.MenuItem("Home", callback=self._on_open_home)
        self._updates_item = rumps.MenuItem("Check for updates...", callback=self._on_check_updates)
        self._paste_last_item = rumps.MenuItem("Paste last transcript", callback=self._on_paste_last)
        self._last_preview_item = rumps.MenuItem("No transcript yet")
        self._last_preview_item.set_callback(None)
        self._shortcuts_header_item = rumps.MenuItem("Shortcuts")
        self._shortcuts_header_item.set_callback(None)
        self._permissions_item = rumps.MenuItem("Open macOS Permissions", callback=self._on_open_permissions)
        self._dictionary_item = rumps.MenuItem("Personal Dictionary", callback=self._on_show_dictionary)
        self._history_item = rumps.MenuItem("Recent Dictations", callback=self._on_show_history)
        self._toggle_item = rumps.MenuItem(f"Toggle Dictation (menu only)", callback=self._on_toggle_from_menu)
        hotkey_hint = "Push-to-talk: hold Fn" if self._fn_supported else f"Push-to-talk: hold {FALLBACK_HOLD_HOTKEY} (Fn not exposed)"
        self._hotkey_hint_item = rumps.MenuItem(hotkey_hint)
        self._hotkey_hint_item.set_callback(None)
        self._paste_shortcut_hint_item = rumps.MenuItem("Paste last transcript shortcut: Cmd+V")
        self._paste_shortcut_hint_item.set_callback(None)
        self._copy_last_item = rumps.MenuItem("Copy Last Processed Speech", callback=self._on_copy_last)
        self._test_overlay_item = rumps.MenuItem("Test Overlay (2s)", callback=self._on_test_overlay)
        self._mic_menu = rumps.MenuItem("Microphone")
        self._mic_items = {}
        self._populate_microphone_menu()
        self._language_menu = rumps.MenuItem("Languages")
        self._language_items = {}
        self._populate_language_menu()
        self._help_item = rumps.MenuItem("Help Center", callback=self._on_open_help)
        self._support_item = rumps.MenuItem("Talk to support", callback=self._on_open_support)
        self._feedback_item = rumps.MenuItem("General feedback", callback=self._on_open_feedback)
        self._model_menu = rumps.MenuItem("Model")
        if installed_models:
            for model_name in installed_models:
                item = rumps.MenuItem(model_name, callback=self._on_select_model)
                item.state = int(model_name == self._selected_model)
                self._model_menu.add(item)
                self._model_items[model_name] = item
        else:
            unavailable = rumps.MenuItem("No local models found")
            unavailable.set_callback(None)
            self._model_menu.add(unavailable)
        self._quit_item = rumps.MenuItem("Quit Whisper Flow", callback=self._on_quit)
        self.menu = [self._home_item, self._updates_item, None, self._paste_last_item, self._last_preview_item, None, self._shortcuts_header_item, self._hotkey_hint_item, self._paste_shortcut_hint_item, None, self._mic_menu, self._language_menu, None, self._dictionary_item, self._history_item, None, self._help_item, self._support_item, self._feedback_item, None, self._status_item, self._permissions_item, self._toggle_item, self._test_overlay_item, self._copy_last_item, self._model_menu, None, self._quit_item]
        if self._fn_supported:
            self._fn_monitor_global = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(NSEventMaskFlagsChanged, self._on_flags_changed)
            self._fn_monitor_local = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(NSEventMaskFlagsChanged, self._on_flags_changed)
        self._hotkey_listener = keyboard.Listener(on_press=self._on_key_press, on_release=self._on_key_release)
        self._hotkey_listener.start()
        self._start_ptt_watchdog()
        self._check_and_prompt_permissions()
        self._app_monitor.start()
        load_models_async(on_complete=self._on_models_ready)

    def _find_default_input_device(self):
        try:
            d, _ = sd.default.device
            return int(d) if d is not None and d >= 0 else None
        except: return None
    def _list_input_devices(self):
        devices = []
        try:
            for idx, device in enumerate(sd.query_devices()):
                if int(device.get("max_input_channels", 0) or 0) > 0:
                    devices.append((idx, str(device.get("name") or f"Input {idx}")))
        except: pass
        return devices
    def _populate_microphone_menu(self):
        devices = self._list_input_devices()
        if not devices:
            self._mic_menu.add(rumps.MenuItem("No input devices found").set_callback(None))
            return
        if self._selected_input_device is None:
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
    def _set_status(self, text):
        self._status_item.title = f"Status: {text}"
    def _set_last_preview(self, text):
        p = (text or "").strip()
        self._last_preview_item.title = (p[:39].rstrip() + "...") if len(p) > 42 else (p or "No transcript yet")
    def _show_overlay(self):
        if self._overlay:
            AppHelper.callAfter(self._overlay.show)
    def _hide_overlay(self):
        if self._overlay:
            AppHelper.callAfter(self._overlay.hide)
    def _set_overlay_preview(self, text):
        if self._overlay:
            AppHelper.callAfter(self._overlay.set_preview_text, text)
    def _tail_words(self, text, limit=LIVE_PREVIEW_WORD_LIMIT):
        w = text.split()
        return " ".join(w[-limit:]) if w else ""
    def _snapshot_preview_audio_locked(self):
        if not self._audio_chunks:
            return None
        target = int(SAMPLE_RATE * LIVE_PREVIEW_WINDOW_SEC)
        min_s = int(SAMPLE_RATE * LIVE_PREVIEW_MIN_AUDIO_SEC)
        c, s = [], 0
        for chunk in reversed(self._audio_chunks):
            f = chunk.reshape(-1)
            c.append(f)
            s += f.size
            if s >= target: break
        if s < min_s:
            return None
        c.reverse()
        snap = np.concatenate(c)
        return (snap[-target:] if snap.size > target else snap).copy()
    def _start_live_preview_locked(self):
        if self._live_preview_thread and self._live_preview_thread.is_alive():
            return
        self._live_preview_model_name = self._selected_model
        self._last_live_preview_text = ""
        self._live_preview_stop_event.clear()
        self._live_preview_thread = threading.Thread(target=self._live_preview_worker, daemon=True)
        self._live_preview_thread.start()
    def _stop_live_preview_locked(self):
        self._live_preview_stop_event.set()
        self._live_preview_thread = None
    def _live_preview_worker(self):
        while not self._live_preview_stop_event.wait(LIVE_PREVIEW_INTERVAL_SEC):
            with self._lock:
                if not self._recording:
                    continue
                m = self._live_preview_model_name or self._selected_model
                a = self._snapshot_preview_audio_locked()
            if a is None:
                continue
            try:
                raw = self._safe_transcribe(m, a, False)
                prev = self._tail_words(raw)
                if prev and prev != self._last_live_preview_text:
                    self._last_live_preview_text = prev
                    self._set_overlay_preview(prev)
            except:
                continue
    def _start_fast_commit_locked(self):
        if self._fast_commit_thread and self._fast_commit_thread.is_alive():
            return
        self._fast_commit_model_name = self._selected_model
        self._fast_commit_stop_event.clear()
        self._fast_chunk_text_segments = []
        self._fast_processed_samples = 0
        with self._audio_buffer_lock:
            self._fast_chunk_queue = []
        self._fast_commit_thread = threading.Thread(target=self._fast_commit_worker, daemon=True)
        self._fast_commit_thread.start()
    def _stop_fast_commit_locked(self):
        self._fast_commit_stop_event.set()
    def _fast_commit_worker(self):
        chunk_s = int(SAMPLE_RATE * FAST_COMMIT_CHUNK_SEC)
        buf = np.zeros(0, dtype=np.float32)
        while not self._fast_commit_stop_event.wait(FAST_COMMIT_POLL_SEC):
            with self._audio_buffer_lock:
                q = self._fast_chunk_queue
                self._fast_chunk_queue = []
            if q:
                buf = np.concatenate([buf, *q])
            while buf.size >= chunk_s:
                chunk = buf[:chunk_s].copy()
                buf = buf[chunk_s:]
                try:
                    text = self._safe_transcribe(self._selected_model, chunk)
                except:
                    text = ""
                with self._lock:
                    self._fast_processed_samples += chunk_s
                    if text:
                        self._fast_chunk_text_segments.append(text)
    def _on_toggle_from_menu(self, _):
        self._toggle_recording()
    def _on_open_home(self, _):
        webbrowser.open(HOME_URL)
    def _on_check_updates(self, _):
        webbrowser.open(UPDATES_URL)
    def _on_test_overlay(self, _):
        self._show_overlay()
        threading.Timer(2.0, self._hide_overlay).start()
    def _on_open_help(self, _):
        webbrowser.open(HELP_CENTER_URL)
    def _on_open_support(self, _):
        webbrowser.open(SUPPORT_URL)
    def _on_open_feedback(self, _):
        webbrowser.open(FEEDBACK_URL)
    def _on_open_permissions(self, _):
        webbrowser.open("x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility")
        webbrowser.open("x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent")
    def _check_and_prompt_permissions(self):
        if self._is_accessibility_trusted() and self._is_input_monitoring_trusted():
            return
        self._request_permissions_prompt()
    def _is_accessibility_trusted(self):
        return AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: False}) if AXIsProcessTrustedWithOptions else True
    def _is_input_monitoring_trusted(self):
        return CGPreflightListenEventAccess() if CGPreflightListenEventAccess else True
    def _request_permissions_prompt(self):
        if AXIsProcessTrustedWithOptions:
            AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})
        if CGRequestListenEventAccess:
            CGRequestListenEventAccess()
    def _key_identifier(self, key):
        if isinstance(key, keyboard.KeyCode):
            return ("char", key.char.lower() if key.char else None)
        return ("key", key)
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
    def _update_ptt_state_locked(self):
        if self._fn_down or self._fallback_down:
            self._start_ptt_if_needed()
        else:
            self._stop_ptt_if_needed()
    def _read_hid_fn_state(self):
        if not (CGEventSourceFlagsState and kCGEventSourceStateHIDSystemState and kCGEventFlagMaskSecondaryFn):
            return None
        try:
            return bool(CGEventSourceFlagsState(kCGEventSourceStateHIDSystemState) & kCGEventFlagMaskSecondaryFn)
        except:
            return None
    def _start_ptt_watchdog(self):
        self._ptt_watchdog_stop_event.clear()
        self._ptt_watchdog_thread = threading.Thread(target=self._ptt_watchdog_worker, daemon=True)
        self._ptt_watchdog_thread.start()
    def _ptt_watchdog_worker(self):
        while not self._ptt_watchdog_stop_event.wait(PTT_STATE_POLL_SEC):
            with self._lock:
                if self._ptt_active and self._ptt_start_time and (time.time() - self._ptt_start_time > PTT_MAX_HOLD_SEC):
                    self._stop_ptt_if_needed()
                    continue
                if not self._fn_supported:
                    continue
            hid = self._read_hid_fn_state()
            with self._lock:
                if hid is not None and self._fn_down != hid:
                    self._fn_down = hid
                    self._update_ptt_state_locked()
    def _on_flags_changed(self, event):
        try:
            f = bool(event.modifierFlags() & NSEventModifierFlagFunction)
        except:
            return event
        with self._lock:
            if self._fn_down != f:
                self._fn_down = f
                self._update_ptt_state_locked()
        return event
    def _on_key_press(self, key):
        self._pressed_keys.add(self._key_identifier(key))
        with self._lock:
            ctrl = any(k in self._pressed_keys for k in [("key", keyboard.Key.ctrl), ("key", keyboard.Key.ctrl_l), ("key", keyboard.Key.ctrl_r)])
            alt = any(k in self._pressed_keys for k in [("key", keyboard.Key.alt), ("key", keyboard.Key.alt_l), ("key", keyboard.Key.alt_r)])
            self._fallback_down = ctrl and alt and (("char", "d") in self._pressed_keys)
            self._update_ptt_state_locked()
    def _on_key_release(self, key):
        kid = self._key_identifier(key)
        if kid in self._pressed_keys:
            self._pressed_keys.remove(kid)
        with self._lock:
            ctrl = any(k in self._pressed_keys for k in [("key", keyboard.Key.ctrl), ("key", keyboard.Key.ctrl_l), ("key", keyboard.Key.ctrl_r)])
            alt = any(k in self._pressed_keys for k in [("key", keyboard.Key.alt), ("key", keyboard.Key.alt_l), ("key", keyboard.Key.alt_r)])
            self._fallback_down = ctrl and alt and (("char", "d") in self._pressed_keys)
            self._update_ptt_state_locked()
    def _copy_to_clipboard(self, text):
        subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
    def _paste_from_clipboard(self):
        with self._keyboard.pressed(keyboard.Key.cmd):
            self._keyboard.press("v")
            self._keyboard.release("v")
    def _on_copy_last(self, _):
        if self._last_processed_text:
            self._copy_to_clipboard(self._last_processed_text)
            self._set_status("Copied last speech")
    def _on_paste_last(self, _):
        if self._last_processed_text:
            self._copy_to_clipboard(self._last_processed_text)
            time.sleep(0.05)
            self._paste_from_clipboard()
            self._set_status("Pasted last speech")
    def _show_injection_failure(self, text, reason):
        _write_clipboard(text)
        rumps.notification("Wispr Local", "Couldn't inject text", f"Copied to clipboard — paste with Cmd+V. ({reason})", sound=False)
    def _on_models_ready(self):
        self.title = "W"
        rumps.notification("Wispr Local", "", "Models ready", sound=False)
    def _on_show_dictionary(self, _):
        words = dict_load()
        response = rumps.Window(message=f"Current: {', '.join(words)}\n\nAdd:", title="Dictionary").run()
        if response.clicked and response.text.strip():
            dict_add(response.text.strip())
    def _on_show_history(self, _):
        entries = history_load()
        msg = "".join(f"[{e.get('app','?')}] {e.get('cleaned','')[:60]}...\n" for e in entries) if entries else "No history."
        rumps.alert("Recent Dictations", message=msg)
    def _on_select_microphone(self, sender):
        selected = sender.title
        entry = self._mic_items.get(selected)
        if entry:
            self._selected_input_device = entry[0]
            for _, item in self._mic_items.values():
                item.state = 0
            sender.state = 1
    def _on_select_language(self, sender):
        l = sender.title
        self._selected_language_label, self._selected_language_code = l, SUPPORTED_LANGUAGES[l]
        for label, item in self._language_items.items():
            item.state = int(label == l)
    def _on_select_model(self, sender):
        m = sender.title
        self._selected_model = m
        for name, item in self._model_items.items():
            item.state = int(name == m)
    def _on_quit(self, _):
        with self._lock:
            self._stop_fast_commit_locked()
            self._stop_live_preview_locked()
            if self._recording:
                self._stop_recording_locked()
        self._stop_ptt_watchdog()
        self._hide_overlay()
        self._hotkey_listener.stop()
        self._app_monitor.stop()
        rumps.quit_application()
    def _audio_callback(self, data, frames, time, status):
        if status: return
        c = data.copy()
        self._audio_chunks.append(c)
        with self._audio_buffer_lock:
            self._fast_chunk_queue.append(c.reshape(-1).copy())
    def _toggle_recording(self):
        with self._lock:
            if not self._recording:
                self._start_recording_locked()
            else:
                self._stop_recording_locked()
    def _start_recording_locked(self):
        try:
            self._show_overlay()
            self._set_status("Recording")
            self.title = "R"
            self._audio_chunks = []
            with self._audio_buffer_lock:
                self._fast_chunk_queue = []
            self._stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="float32", device=self._selected_input_device, callback=self._audio_callback)
            self._stream.start()
            self._recording = True
            self._start_fast_commit_locked()
            self._start_live_preview_locked()
        except Exception as e:
            self._recording = False
            self.title = "W"
            self._set_status(f"Mic error: {e}")
            self._hide_overlay()
    def _stop_recording_locked(self):
        self._stop_fast_commit_locked()
        self._stop_live_preview_locked()
        if self._stream:
            self._stream.stop()
            self._stream.close()
        self._recording = False
        self.title = "W"
        self._hide_overlay()
        if not self._audio_chunks:
            return
        cap = np.concatenate(self._audio_chunks).reshape(-1)
        self._audio_chunks = []
        fs = list(self._fast_chunk_text_segments)
        fp = int(self._fast_processed_samples)
        self._fast_chunk_text_segments = []
        self._fast_processed_samples = 0
        threading.Thread(target=self._finalize_and_type, args=(cap, self._selected_model, self._selected_model, fs, fp), daemon=True).start()
    def _safe_transcribe(self, m, a, p=True):
        return self._safe_transcribe_static(m, a, self._selected_language_code, as_prompt() if p else None, self._inference_lock)
    @staticmethod
    def _safe_transcribe_static(m, a, l="en", pr=None, lock=None):
        if a is None or a.size == 0 or np.sqrt(np.mean(a**2)) < 0.01:
            return ""
        if VAD_AVAILABLE:
            t = torch.from_numpy(a).float()
            ts = GET_SPEECH_TIMESTAMPS(t, VAD_MODEL, sampling_rate=SAMPLE_RATE, threshold=0.8)
            if not ts:
                return ""
            a = t[max(0, ts[0]['start']-1600):min(t.size(0), ts[-1]['end']+1600)].numpy()
        rms = np.sqrt(np.mean(a**2))
        if rms > 0.005:
            a = np.clip(a * (min(AUDIO_NORM_TARGET_RMS / rms, 2.0)), -1.0, 1.0)
        try:
            model = get_model_by_name(m)
            kwargs = {"temperature": 0, "initial_prompt": pr, "verbose": False, "no_speech_threshold": 0.8, "logprob_threshold": -1.0, "compression_ratio_threshold": 2.4, "condition_on_previous_text": False, "language": l}
            if lock:
                with lock:
                    r = model.transcribe(a, **kwargs)
            else:
                r = model.transcribe(a, **kwargs)
            raw = " ".join(s["text"].strip() for s in r["segments"] if s.get("no_speech_prob", 0) < 0.2 and s.get("avg_logprob", -1.0) > -0.5).strip()
            import re
            clean_t = re.sub(r'[^\w\s]', '', raw.lower()).strip()
            if clean_t in ["thank you", "thanks for watching", "subtitle", "please subscribe", "the end"]:
                return ""
            return raw if len(raw) >= 4 else ""
        except:
            return ""
    def _finalize_and_type(self, a, m, fm, fs, fp):
        try:
            raw = ""
            if (a.size / SAMPLE_RATE) <= SHORT_UTTERANCE_FAST_PATH_SEC:
                raw = self._safe_transcribe(m, a)
            elif fs:
                raw = " ".join(fs).strip()
                rem = a[min(fp, a.size):]
                if rem.size >= int(SAMPLE_RATE * FAST_COMMIT_MIN_TAIL_SEC):
                    tail = self._safe_transcribe(m, rem)
                    if tail:
                        raw = f"{raw} {tail}".strip()
            if not raw:
                raw = self._safe_transcribe(m, a)
            app = self._app_monitor.get()
            cleaned, ms = (raw, 0) if len(raw.split()) < 3 else clean(raw, app)
            formatted = format_transcript(cleaned)
            if not formatted or len(formatted.strip()) < 4:
                AppHelper.callAfter(self._set_status, "No speech recognized")
                return
            self._last_processed_text = formatted
            RUNTIME_LAST_TEXT_PATH.write_text(formatted, encoding="utf-8")
            AppHelper.callAfter(self._set_last_preview, formatted)
            success, reason = inject(formatted, app)
            if success:
                AppHelper.callAfter(self._set_status, f"Pasted")
                rumps.notification("Whisper Dictation", "Transcription inserted")
            else:
                AppHelper.callAfter(self._show_injection_failure, formatted, reason)
            history_save(raw, formatted, app, ms)
        except Exception as e:
            self._set_status(f"Error: {e}")

def main():
    app = WhisperMenuBarApp()
    if RUNTIME_LAST_TEXT_PATH.exists():
        try:
            app._last_processed_text = RUNTIME_LAST_TEXT_PATH.read_text(encoding="utf-8").strip()
            app._set_last_preview(app._last_processed_text)
        except:
            pass
    app.run()

if __name__ == "__main__":
    main()
