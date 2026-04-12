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

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = PROJECT_ROOT / "src"
CONFIG_DIR = PROJECT_ROOT / "config"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(CONFIG_DIR) not in sys.path:
    sys.path.insert(0, str(CONFIG_DIR))

import os

# Suppress annoying Objective-C duplicated class warnings from PyAV vs Homebrew FFmpeg
old_stderr = os.dup(2)
devnull = os.open(os.devnull, os.O_WRONLY)
os.dup2(devnull, 2)
try:
    from src.apps.web.app import format_transcript, get_default_model_name, get_installed_models, get_model_by_name
    from src.shared.llm_cleanup import clean, warmup  # LLM layer ENABLED - hybrid approach with rule-based formatting
    from src.shared.text_injector import AppMonitor, inject, _write_clipboard
    from src.apps.macos.warmup import load_models_async
    from src.shared.dictionary import load as dict_load, add as dict_add, as_prompt
    from src.shared.history import save as history_save, load as history_load
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
FAST_COMMIT_CHUNK_SEC = 0.35
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
    """
    Get the name of the currently active application on macOS.
    Returns the bundle identifier or process name.
    """
    if not APPKIT_AVAILABLE:
        return ""
    
    try:
        from AppKit import NSWorkspace
        workspace = NSWorkspace.sharedWorkspace()
        active_app = workspace.activeApplication()
        if active_app:
            # Try to get bundle identifier first, fall back to process name
            bundle_id = active_app.get('NSApplicationBundleIdentifier', '')
            process_name = active_app.get('NSApplicationName', '')
            return bundle_id or process_name or ""
        return ""
    except Exception:  # noqa: BLE001
        return ""


def trim_silence(audio: np.ndarray) -> Optional[np.ndarray]:
    """
    Trim silence from audio using Silero VAD.
    Returns trimmed audio tensor or None if pure silence.
    """
    if not VAD_AVAILABLE or audio.size == 0:
        return audio
    
    try:
        # Convert numpy array to torch tensor if needed
        if isinstance(audio, np.ndarray):
            wav_tensor = torch.from_numpy(audio).float()
        else:
            wav_tensor = audio
        
        # Run VAD to get speech timestamps
        # Threshold: 0.8 (up from 0.5) ensures background hum/noise is ignored.
        timestamps = GET_SPEECH_TIMESTAMPS(wav_tensor, VAD_MODEL, sampling_rate=SAMPLE_RATE, threshold=0.8)
        
        # No speech detected — skip transcription
        if not timestamps:
            return None
        
        # Extract speech regions
        start = timestamps[0]['start']
        end = timestamps[-1]['end']
        return wav_tensor[start:end].numpy()
    except Exception:  # noqa: BLE001
        # If VAD fails, return original audio
        return audio


def transcribe_with_timing(
    audio: np.ndarray,
    model_name: str = "turbo",
    language: Optional[str] = "en",
    normalize_audio: bool = True,
) -> dict:
    """
    Transcribe audio with detailed latency measurement at each stage.
    
    Phase 1 validation function to measure:
    - VAD (Voice Activity Detection) time
    - ASR (Automatic Speech Recognition) time
    - PCL (Post-Conversion Layer / text formatting) time
    
    Args:
        audio: numpy array of audio samples (16kHz mono)
        model_name: Faster-Whisper model to use
        language: Language code (e.g., "en")
        normalize_audio: Whether to normalize audio amplitude
    
    Returns:
        dict with keys:
        - 'vad_ms': VAD processing time in milliseconds
        - 'asr_ms': Transcription time in milliseconds
        - 'pcl_ms': Text formatting time in milliseconds
        - 'total_ms': Total pipeline time in milliseconds
        - 'raw_text': Raw ASR output
        - 'cleaned_text': Formatted text
        - 'had_speech': Whether speech was detected
    """
    t0 = time.time()
    
    # Stage 1: VAD (Voice Activity Detection)
    trimmed = trim_silence(audio)
    t1 = time.time()
    vad_ms = (t1 - t0) * 1000
    
    # If no speech detected, return early
    if trimmed is None:
        t_done = time.time()
        return {
            'vad_ms': vad_ms,
            'asr_ms': 0,
            'pcl_ms': 0,
            'total_ms': (t_done - t0) * 1000,
            'raw_text': "",
            'cleaned_text': "",
            'had_speech': False,
        }
    
    # Convert back to numpy if needed
    if isinstance(trimmed, torch.Tensor):
        trimmed = trimmed.numpy()
    
    # Optional: normalize audio for quiet speech
    if normalize_audio:
        trimmed = _normalize_audio_for_quiet_speech_static(trimmed)
    
    # Stage 2: ASR (Transcription)
    t1_5 = time.time()
    try:
        # Use unified safe transcription to block hallucinations
        raw_text = WhisperMenuBarApp._safe_transcribe_static(
            model_name, 
            trimmed, 
            language=language or "en",
            initial_prompt=None # Static path doesn't use dict prompt
        )
        
        t2 = time.time()
        asr_ms = (t2 - t1_5) * 1000
    except Exception as e:  # noqa: BLE001
        print(f"Error during ASR: {e}")
        return {
            'vad_ms': vad_ms,
            'asr_ms': 0,
            'pcl_ms': 0,
            'total_ms': (time.time() - t0) * 1000,
            'raw_text': "",
            'cleaned_text': "",
            'had_speech': True,
            'error': str(e),
        }
    
    # Stage 3: PCL (Post-Conversion Layer / Hybrid LLM + Rule-based Formatting)
    t2_5 = time.time()
    
    # Stage 3a: LLM cleanup (advanced)
    llm_cleaned_text, llm_ms = clean(raw_text, model_name)
    
    # Stage 3b: Rule-based formatting polish
    cleaned_text = format_transcript(llm_cleaned_text)
    t3 = time.time()
    pcl_ms = (t3 - t2_5) * 1000
    
    total_ms = (t3 - t0) * 1000
    
    return {
        'vad_ms': vad_ms,
        'asr_ms': asr_ms,
        'pcl_ms': pcl_ms,
        'total_ms': total_ms,
        'raw_text': raw_text,
        'cleaned_text': cleaned_text,
        'had_speech': True,
    }


def _normalize_audio_for_quiet_speech_static(audio: np.ndarray) -> np.ndarray:
    """
    Static version of audio normalization (without self reference).
    Boost quiet speech to standard loudness for better model input.
    """
    if audio.size == 0:
        return audio
    rms = np.sqrt(np.mean(audio**2))
    if rms < 0.001:  # Near-silent, leave as-is.
        return audio
    scale = AUDIO_NORM_TARGET_RMS / rms
    # Limit to 3x boost to avoid clipping artifacts.
    scale = min(scale, 3.0)
    return np.clip(audio * scale, -1.0, 1.0)


def _filter_hallucinations(text: str) -> str:
    """
    Filter out hallucinated text patterns that Whisper commonly generates.
    
    Aggressive detection of:
    - Single words/phrases repeated excessively (>10% of transcript)
    - Filler-heavy transcriptions (>30% fillers and pronouns)
    
    Args:
        text: Raw transcription text from Whisper
        
    Returns:
        Filtered text with hallucinations removed
    """
    if not text or len(text.strip()) < 3:
        return text
    
    words = text.split()
    if not words:
        return text
    
    total_words = len(words)
    
    # Count word frequencies
    word_counts = {}
    for word in words:
        normalized = word.lower().rstrip('.,!?;:')
        word_counts[normalized] = word_counts.get(normalized, 0) + 1
    
    # Find the most repeated word
    if word_counts:
        most_common_word = max(word_counts, key=word_counts.get)
        most_common_count = word_counts[most_common_word]
        
        # If any single word is >10% of text, it's likely a hallucination
        if most_common_count / total_words > 0.1:
            # Remove all instances of this dominant hallucination word
            filtered_words = [
                w for w in words
                if w.lower().rstrip('.,!?;:') != most_common_word
            ]
            if filtered_words:
                # Recursively apply filter to catch secondary hallucinations
                return _filter_hallucinations(" ".join(filtered_words))
            return ""
    
    # Filler/pronoun detection
    hallucination_indicators = {
        'you', 'i', 'uh', 'um', 'ah', 'so', 'ok', 'thank', 'well', 'like', 'just'
    }
    
    hallucin_count = sum(
        1 for word in words 
        if word.lower().rstrip('.,!?;:') in hallucination_indicators
    )
    
    # If >30% are fillers, extract only content
    if hallucin_count / total_words > 0.3:
        real_words = [
            w for w in words 
            if w.lower().rstrip('.,!?;:') not in hallucination_indicators
        ]
        if real_words and len(real_words) >= 3:
            return " ".join(real_words)
        return ""
    
    # Strip leading/trailing junk
    start_idx = 0
    for i, word in enumerate(words):
        normalized = word.lower().rstrip('.,!?;:')
        if normalized not in hallucination_indicators and len(normalized) > 1:
            start_idx = i
            break
    
    end_idx = len(words) - 1
    for i in range(len(words) - 1, -1, -1):
        normalized = words[i].lower().rstrip('.,!?;:')
        if normalized not in hallucination_indicators and len(normalized) > 1:
            end_idx = i
            break
    
    if start_idx <= end_idx:
        return " ".join(words[start_idx:end_idx + 1]).strip()
    
    return ""


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
            if NSMouseInRect(mouse_point, screen.frame(), False):
                return screen
        return NSScreen.mainScreen()

    def _layout_content(self):
        width = self.pill_width
        height = self.pill_height

        title_frame = NSMakeRect(58, height - 34, width - 70, 20)
        preview_frame = NSMakeRect(58, 40, width - 70, 26)
        hint_frame = NSMakeRect(58, 14, width - 70, 18)
        spinner_frame = NSMakeRect(20, (height - 20) / 2, 20, 20)

        self.title_label.setFrame_(title_frame)
        self.preview_label.setFrame_(preview_frame)
        self.hint_label.setFrame_(hint_frame)
        self.spinner.setFrame_(spinner_frame)

    def _build_window(self):
        screen = NSScreen.mainScreen()
        screen_frame = screen.frame()
        frame = self._pill_frame_for_screen(screen_frame)

        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            frame,
            NSWindowStyleMaskBorderless,
            NSBackingStoreBuffered,
            False,
        )
        self.window.setReleasedWhenClosed_(False)
        self.window.setOpaque_(False)
        self.window.setBackgroundColor_(NSColor.colorWithCalibratedRed_green_blue_alpha_(0.06, 0.06, 0.08, 0.86))
        self.window.setIgnoresMouseEvents_(True)
        self.window.setLevel_(NSScreenSaverWindowLevel)
        self.window.setHasShadow_(True)
        self.window.setHidesOnDeactivate_(False)
        self.window.setCanHide_(False)
        self.window.setCollectionBehavior_(
            NSWindowCollectionBehaviorFullScreenAuxiliary
            | NSWindowCollectionBehaviorMoveToActiveSpace
        )
        self.window.setMovable_(False)

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
        if not self.preview_label:
            return
        value = (text or "").strip() or "Listening..."
        self.preview_label.setStringValue_(value)


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
        self._fn_monitor = None
        self._ptt_watchdog_stop_event = threading.Event()
        self._ptt_watchdog_thread = None
        self._ptt_start_time = None  # Track when PTT started for timeout
        self._live_preview_thread = None
        self._live_preview_stop_event = threading.Event()
        self._inference_lock = threading.Lock()
        self._audio_buffer_lock = threading.Lock()
        self._live_preview_model_name: Optional[str] = None
        self._last_live_preview_text = ""
        self._fast_commit_thread = None
        self._fast_commit_stop_event = threading.Event()
        self._fast_chunk_queue = []
        self._fast_chunk_text_segments = []
        self._fast_processed_samples = 0
        self._fast_commit_model_name: Optional[str] = None
        self._selected_language_label = "English"
        self._selected_language_code: Optional[str] = "en"
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

        self._toggle_item = rumps.MenuItem(
            f"Toggle Dictation (menu only)",
            callback=self._on_toggle_from_menu,
        )

        hotkey_hint = (
            "Push-to-talk: hold Fn"
            if self._fn_supported
            else f"Push-to-talk: hold {FALLBACK_HOLD_HOTKEY} (Fn not exposed)"
        )
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
        self.menu = [
            self._home_item,
            self._updates_item,
            None,
            self._paste_last_item,
            self._last_preview_item,
            None,
            self._shortcuts_header_item,
            self._hotkey_hint_item,
            self._paste_shortcut_hint_item,
            None,
            self._mic_menu,
            self._language_menu,
            None,
            self._dictionary_item,
            self._history_item,
            None,
            self._help_item,
            self._support_item,
            self._feedback_item,
            None,
            self._status_item,
            self._permissions_item,
            self._toggle_item,
            self._test_overlay_item,
            self._copy_last_item,
            self._model_menu,
            None,
            self._quit_item,
        ]

        if self._fn_supported:
            # Register both global and local monitors to ensure robust key detection
            # in all application states (especially when the dictation overlay is shown).
            self._fn_monitor_global = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                NSEventMaskFlagsChanged,
                self._on_flags_changed,
            )
            self._fn_monitor_local = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
                NSEventMaskFlagsChanged,
                self._on_flags_changed,
            )

        self._hotkey_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self._hotkey_listener.start()
        self._start_ptt_watchdog()

        self._check_and_prompt_permissions()
        
        # Start active app monitor (runs in background, updates every 0.5s)
        self._app_monitor.start()
        
        # Background warmup of Whisper models (primary + preview) and Ollama LLM
        # This eliminates the latency spike on first key press and first clean call
        load_models_async(on_complete=self._on_models_ready)

    def _find_default_input_device(self) -> Optional[int]:
        try:
            default_input, _ = sd.default.device
            if default_input is None or default_input < 0:
                return None
            return int(default_input)
        except Exception:  # noqa: BLE001
            return None


    def _warmup_ollama_async(self):
        """
        Warm up the Ollama LLM cleanup model at startup with a dummy call.
        This eliminates the ~1500ms first-run latency spike on first cleanup.
        Runs in background thread so it doesn't block the UI.
        """
        def ollama_warmup():
            try:
                warmup()
            except Exception:  # noqa: BLE001
                # Silently ignore warmup errors
                pass
        
        ollama_thread = threading.Thread(target=ollama_warmup, daemon=True)
        ollama_thread.start()

    def _list_input_devices(self):
        devices = []
        try:
            for idx, device in enumerate(sd.query_devices()):
                max_inputs = int(device.get("max_input_channels", 0) or 0)
                if max_inputs <= 0:
                    continue
                name = str(device.get("name") or f"Input {idx}")
                devices.append((idx, name))
        except Exception:  # noqa: BLE001
            return []
        return devices

    def _populate_microphone_menu(self):
        devices = self._list_input_devices()
        if not devices:
            item = rumps.MenuItem("No input devices found")
            item.set_callback(None)
            self._mic_menu.add(item)
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

    def _tail_words(self, text: str, word_limit: int = LIVE_PREVIEW_WORD_LIMIT) -> str:
        words = text.split()
        if not words:
            return ""
        return " ".join(words[-word_limit:])

    def _normalize_audio_for_quiet_speech(self, audio: np.ndarray) -> np.ndarray:
        # Boost quiet speech (whisper) to standard loudness for better model input.
        if audio.size == 0:
            return audio
        rms = np.sqrt(np.mean(audio**2))
        # Aggressive noise floor: raise to 0.01 to ignore persistent low-level static.
        if rms < 0.01:
            return audio
        scale = AUDIO_NORM_TARGET_RMS / rms
        scale = min(scale, 2.0)
        return np.clip(audio * scale, -1.0, 1.0)

    def _get_preview_model_name(self) -> str:
        installed = get_installed_models()
        if not installed:
            return self._selected_model

        for candidate in LIVE_PREVIEW_MODEL_PREFERENCE:
            if candidate in installed:
                return candidate

        if self._selected_model in installed:
            return self._selected_model
        return installed[0]

    def _snapshot_preview_audio_locked(self) -> Optional[np.ndarray]:
        if not self._audio_chunks:
            return None

        target_samples = int(SAMPLE_RATE * LIVE_PREVIEW_WINDOW_SEC)
        min_samples = int(SAMPLE_RATE * LIVE_PREVIEW_MIN_AUDIO_SEC)
        collected = []
        collected_samples = 0

        for chunk in reversed(self._audio_chunks):
            flattened = chunk.reshape(-1)
            collected.append(flattened)
            collected_samples += flattened.size
            if collected_samples >= target_samples:
                break

        if collected_samples < min_samples:
            return None

        collected.reverse()
        snapshot = np.concatenate(collected)
        if snapshot.size > target_samples:
            snapshot = snapshot[-target_samples:]
        return snapshot.copy()

    def _start_live_preview_locked(self):
        if self._live_preview_thread and self._live_preview_thread.is_alive():
            return
        self._live_preview_model_name = self._get_preview_model_name()
        self._last_live_preview_text = ""
        self._live_preview_stop_event.clear()
        self._set_overlay_preview("Listening...")
        self._live_preview_thread = threading.Thread(target=self._live_preview_worker, daemon=True)
        self._live_preview_thread.start()

    def _stop_live_preview_locked(self):
        self._live_preview_stop_event.set()
        self._live_preview_thread = None
        self._last_live_preview_text = ""

    def _live_preview_worker(self):
        while not self._live_preview_stop_event.wait(LIVE_PREVIEW_INTERVAL_SEC):
            with self._lock:
                if not self._recording:
                    continue
                preview_model_name = self._live_preview_model_name or self._selected_model
                audio_snapshot = self._snapshot_preview_audio_locked()

            if audio_snapshot is None:
                continue

            try:
                # Use unified safe transcription logic for live preview bubble
                raw_text = self._safe_transcribe(
                    preview_model_name, 
                    audio_snapshot, 
                    use_initial_prompt=False # Skip dictionary bias for preview
                )
                preview_text = self._tail_words(raw_text)

                if preview_text and preview_text != self._last_live_preview_text:
                    self._last_live_preview_text = preview_text
                    self._set_overlay_preview(preview_text)
            except Exception:  # noqa: BLE001
                # Ignore live preview errors so push-to-talk keeps running.
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

    def _drain_fast_queue(self):
        with self._audio_buffer_lock:
            if not self._fast_chunk_queue:
                return []
            queued = self._fast_chunk_queue
            self._fast_chunk_queue = []
            return queued

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
                    # Use unified safe transcription logic for background chunks
                    raw_text = self._safe_transcribe(model_name, audio_chunk)
                except Exception:  # noqa: BLE001
                    raw_text = ""

                with self._lock:
                    self._fast_processed_samples += chunk_samples
                    if raw_text:
                        self._fast_chunk_text_segments.append(raw_text)

    def _on_toggle_from_menu(self, _):
        self._toggle_recording()

    def _on_open_home(self, _):
        webbrowser.open(HOME_URL)
        self._set_status("Opened Home")

    def _on_check_updates(self, _):
        webbrowser.open(UPDATES_URL)
        self._set_status("Opened updates page")

    def _on_test_overlay(self, _):
        self._show_overlay()
        threading.Timer(2.0, self._hide_overlay).start()

    def _on_open_help(self, _):
        webbrowser.open(HELP_CENTER_URL)
        self._set_status("Opened Help Center")

    def _on_open_support(self, _):
        webbrowser.open(SUPPORT_URL)
        self._set_status("Opened support")

    def _on_open_feedback(self, _):
        webbrowser.open(FEEDBACK_URL)
        self._set_status("Opened feedback")

    def _is_accessibility_trusted(self) -> bool:
        if AXIsProcessTrustedWithOptions is None:
            return True
        try:
            return bool(AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: False}))
        except Exception:  # noqa: BLE001
            return True

    def _is_input_monitoring_trusted(self) -> bool:
        if CGPreflightListenEventAccess is None:
            return True
        try:
            return bool(CGPreflightListenEventAccess())
        except Exception:  # noqa: BLE001
            return True

    def _request_permissions_prompt(self):
        try:
            if AXIsProcessTrustedWithOptions is not None:
                AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})
        except Exception:  # noqa: BLE001
            pass

        try:
            if CGRequestListenEventAccess is not None:
                CGRequestListenEventAccess()
        except Exception:  # noqa: BLE001
            pass

    def _on_open_permissions(self, _):
        webbrowser.open("x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility")
        webbrowser.open("x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent")
        self._set_status("Opened Accessibility/Input Monitoring settings")

    def _check_and_prompt_permissions(self):
        accessibility_ok = self._is_accessibility_trusted()
        input_ok = self._is_input_monitoring_trusted()

        if accessibility_ok and input_ok:
            return

        self._request_permissions_prompt()
        if not accessibility_ok and not input_ok:
            self._set_status("Grant Accessibility + Input Monitoring, then relaunch")
        elif not accessibility_ok:
            self._set_status("Grant Accessibility permission, then relaunch")
        else:
            self._set_status("Grant Input Monitoring permission, then relaunch")

    def _key_identifier(self, key):
        if isinstance(key, keyboard.KeyCode):
            char = key.char.lower() if key.char else None
            return ("char", char)
        return ("key", key)

    def _start_ptt_if_needed(self):
        if self._ptt_active:
            return
        self._ptt_active = True
        self._ptt_start_time = time.time()  # Record when PTT started
        if not self._recording:
            self._start_recording_locked()

    def _stop_ptt_if_needed(self):
        if not self._ptt_active:
            return
        self._ptt_active = False
        self._ptt_start_time = None  # Clear PTT start time
        if self._recording:
            self._stop_recording_locked()

    def _update_ptt_state_locked(self):
        should_be_active = self._fn_down or self._fallback_down
        if should_be_active:
            self._start_ptt_if_needed()
        else:
            self._stop_ptt_if_needed()

    def _read_hid_fn_state(self) -> Optional[bool]:
        if (
            CGEventSourceFlagsState is None
            or kCGEventSourceStateHIDSystemState is None
            or kCGEventFlagMaskSecondaryFn is None
        ):
            return None
        try:
            flags = CGEventSourceFlagsState(kCGEventSourceStateHIDSystemState)
            return bool(flags & kCGEventFlagMaskSecondaryFn)
        except Exception:  # noqa: BLE001
            return None

    def _start_ptt_watchdog(self):
        if self._ptt_watchdog_thread and self._ptt_watchdog_thread.is_alive():
            return
        self._ptt_watchdog_stop_event.clear()
        self._ptt_watchdog_thread = threading.Thread(target=self._ptt_watchdog_worker, daemon=True)
        self._ptt_watchdog_thread.start()

    def _stop_ptt_watchdog(self):
        self._ptt_watchdog_stop_event.set()

    def _ptt_watchdog_worker(self):
        while not self._ptt_watchdog_stop_event.wait(PTT_STATE_POLL_SEC):
            with self._lock:
                # Timeout check: Force-stop PTT if held for too long
                if self._ptt_active and self._ptt_start_time:
                    elapsed = time.time() - self._ptt_start_time
                    if elapsed > PTT_MAX_HOLD_SEC:
                        print(f"⚠️  PTT timeout after {elapsed:.0f}s — force-stopping")
                        self._stop_ptt_if_needed()
                        continue
                
                # Only check HID if Fn is supported
                if not self._fn_supported:
                    continue

            hid_fn_down = self._read_hid_fn_state()
            
            with self._lock:
                # If HID read fails but we were previously down, try forcing release
                if hid_fn_down is None:
                    if self._fn_down and self._ptt_active:
                        # HID unavailable after holding - force reset
                        print("⚠️  HID state unavailable — resetting Fn state")
                        self._fn_down = False
                        self._update_ptt_state_locked()
                    continue
                
                # Update state if changed
                if self._fn_down != hid_fn_down:
                    self._fn_down = hid_fn_down
                    self._update_ptt_state_locked()

    def _on_flags_changed(self, event):
        try:
            fn_down = bool(event.modifierFlags() & NSEventModifierFlagFunction)
        except Exception:  # noqa: BLE001
            return event

        with self._lock:
            if self._fn_down != fn_down:
                self._fn_down = fn_down
                self._update_ptt_state_locked()
        
        return event

    def _is_fallback_combo_active(self) -> bool:
        ctrl_down = (
            ("key", keyboard.Key.ctrl) in self._pressed_keys
            or ("key", keyboard.Key.ctrl_l) in self._pressed_keys
            or ("key", keyboard.Key.ctrl_r) in self._pressed_keys
        )
        alt_down = (
            ("key", keyboard.Key.alt) in self._pressed_keys
            or ("key", keyboard.Key.alt_l) in self._pressed_keys
            or ("key", keyboard.Key.alt_r) in self._pressed_keys
        )
        d_down = ("char", "d") in self._pressed_keys
        return ctrl_down and alt_down and d_down

    def _is_ptt_trigger_active(self) -> bool:
        return self._is_fallback_combo_active()

    def _on_key_press(self, key):
        key_id = self._key_identifier(key)
        self._pressed_keys.add(key_id)

        with self._lock:
            self._fallback_down = self._is_ptt_trigger_active()
            self._update_ptt_state_locked()

    def _on_key_release(self, key):
        key_id = self._key_identifier(key)
        if key_id in self._pressed_keys:
            self._pressed_keys.remove(key_id)

        with self._lock:
            self._fallback_down = self._is_ptt_trigger_active()
            self._update_ptt_state_locked()

    def _copy_to_clipboard(self, text: str):
        subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)

    def _paste_from_clipboard(self):
        with self._keyboard.pressed(keyboard.Key.cmd):
            self._keyboard.press("v")
            self._keyboard.release("v")

    def _on_copy_last(self, _):
        if not self._last_processed_text:
            self._set_status("No processed speech to copy")
            return
        try:
            self._copy_to_clipboard(self._last_processed_text)
            self._set_status("Copied last processed speech")
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Copy failed: {exc}")

    def _on_paste_last(self, _):
        if not self._last_processed_text:
            self._set_status("No processed speech to paste")
            return
        try:
            self._copy_to_clipboard(self._last_processed_text)
            time.sleep(0.05)
            self._paste_from_clipboard()
            self._set_status("Pasted last processed speech")
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Paste failed: {exc}")

    def _show_injection_failure(self, text: str, reason: str):
        """
        Handle text injection failure by putting text on clipboard
        and notifying user so they can paste manually.
        """
        print(f"✗ Injection failed: {reason}")
        
        # Put text on clipboard so user can manually paste with Cmd+V
        try:
            _write_clipboard(text)
        except Exception as e:  # noqa: BLE001
            print(f"Failed to copy to clipboard: {e}")
            return
        
        # Notify via macOS notification
        rumps.notification(
            "Wispr Local",
            "Couldn't inject text",
            f"Copied to clipboard — paste with Cmd+V. ({reason})",
            sound=False
        )
        
        self._set_status(f"Injection failed: {reason} — text on clipboard")

    def _on_models_ready(self):
        """Called when warmup models are ready."""
        self.title = "W"  # Signal ready
        rumps.notification("Wispr Local", "", "Models ready", sound=False)

    def _on_show_dictionary(self, _):
        """Show personal dictionary UI."""
        words = dict_load()
        current = ", ".join(words) if words else "Empty"
        response = rumps.Window(
            message=f"Current words: {current}\n\nAdd a word:",
            title="Personal Dictionary",
            default_text="",
            ok="Add",
            cancel="Close"
        ).run()
        if response.clicked and response.text.strip():
            dict_add(response.text.strip())
            rumps.notification("Dictionary", "", f"Added: {response.text.strip()}")

    def _on_show_history(self, _):
        """Show recent dictations history."""
        entries = history_load()
        if not entries:
            rumps.alert("No history yet.")
            return
        msg = ""
        for e in entries:
            timestamp = e.get("timestamp", "").split("T")[0]  # Extract date
            app = e.get("app", "unknown")
            text = e.get("cleaned", "")[:60]  # Truncate to 60 chars
            msg += f"[{app}] {text}...\n"
        rumps.alert("Recent Dictations", message=msg)

    def _on_select_microphone(self, sender):
        selected = sender.title
        selected_entry = self._mic_items.get(selected)
        if selected_entry is None:
            return

        selected_device_id, _ = selected_entry
        self._selected_input_device = selected_device_id

        for _, item in self._mic_items.values():
            item.state = 0
        sender.state = 1

        self._set_status(f"Microphone set: {selected}")

    def _on_select_language(self, sender):
        selected = sender.title
        if selected not in SUPPORTED_LANGUAGES:
            return

        self._selected_language_label = selected
        self._selected_language_code = SUPPORTED_LANGUAGES[selected]
        for label, item in self._language_items.items():
            item.state = int(label == selected)
        self._set_status(f"Language: {selected}")

    def _on_select_model(self, sender):
        selected = sender.title
        self._selected_model = selected
        for model_name, item in self._model_items.items():
            item.state = int(model_name == selected)
        self._set_status(f"Model set to {selected}")

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

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            return
        # Keep callback non-blocking; holding the main lock here can deadlock stream stop.
        chunk = indata.copy()
        self._audio_chunks.append(chunk)
        with self._audio_buffer_lock:
            self._fast_chunk_queue.append(chunk.reshape(-1).copy())

    def _toggle_recording(self):
        with self._lock:
            if not self._recording:
                self._start_recording_locked()
            else:
                self._stop_recording_locked()

    def _start_recording_locked(self):
        try:
            # Shift overlay display to the VERY FIRST step for instant UI feedback
            self._show_overlay()
            self._set_status("Recording")
            self.title = "R"
            
            self._audio_chunks = []
            with self._audio_buffer_lock:
                self._fast_chunk_queue = []
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="float32",
                device=self._selected_input_device,
                callback=self._audio_callback,
            )
            self._stream.start()
            self._recording = True
            
            self._start_fast_commit_locked()
            self._start_live_preview_locked()
        except Exception as exc:  # noqa: BLE001
            self._recording = False
            self._stream = None
            self.title = "W"
            self._set_status(f"Mic error: {exc}")
            self._hide_overlay()

    def _stop_recording_locked(self):
        self._stop_fast_commit_locked()
        self._stop_live_preview_locked()

        if self._stream is not None:
            self._stream.stop()
            self._stream.close()

        self._recording = False
        self.title = "W"
        self._hide_overlay()

        if not self._audio_chunks:
            self._set_status("No audio captured")
            return

        captured = np.concatenate(self._audio_chunks, axis=0).reshape(-1)
        self._audio_chunks = []

        if captured.size == 0:
            self._set_status("No audio captured")
            return

        fast_segments = list(self._fast_chunk_text_segments)
        fast_processed_samples = int(self._fast_processed_samples)
        fast_model_name = self._fast_commit_model_name or self._selected_model
        self._fast_chunk_text_segments = []
        self._fast_processed_samples = 0
        self._fast_commit_model_name = None

        self._set_status("Transcribing")
        threading.Thread(
            target=self._finalize_and_type,
            args=(captured.copy(), self._selected_model, fast_model_name, fast_segments, fast_processed_samples),
            daemon=True,
        ).start()

    def _safe_transcribe(self, model_name: str, audio: np.ndarray, use_initial_prompt: bool = True) -> str:
        """Central transcription hub with integrated hallucination defense."""
        prompt = as_prompt() if use_initial_prompt else None
        return self._safe_transcribe_static(
            model_name, 
            audio, 
            language=self._selected_language_code or "en",
            initial_prompt=prompt,
            inference_lock=self._inference_lock
        )

    @staticmethod
    def _safe_transcribe_static(
        model_name: str, 
        audio: np.ndarray, 
        language: str = "en", 
        initial_prompt: str = None,
        inference_lock: threading.Lock = None
    ) -> str:
        if audio is None or audio.size == 0:
            return ""

        # 1. Noise Floor Guard (0.01 RMS)
        rms = np.sqrt(np.mean(audio**2))
        if rms < 0.01:
            return ""

        # 2. VAD Guard (Strict 0.8)
        if VAD_AVAILABLE:
            wav_tensor = torch.from_numpy(audio).float() if isinstance(audio, np.ndarray) else audio
            timestamps = GET_SPEECH_TIMESTAMPS(wav_tensor, VAD_MODEL, sampling_rate=SAMPLE_RATE, threshold=0.8)
            if not timestamps:
                return ""
            # Trim to speech region
            audio = wav_tensor[max(0, timestamps[0]['start']-1600):min(wav_tensor.size(0), timestamps[-1]['end']+1600)].numpy()

        # 3. Normalization
        rms = np.sqrt(np.mean(audio**2))
        if rms > 0.005:
            scale = min(AUDIO_NORM_TARGET_RMS / rms, 2.0)
            audio = np.clip(audio * scale, -1.0, 1.0)

        # 4. Transcription with confidence thresholds
        try:
            model = get_model_by_name(model_name)
            transcribe_kwargs = {
                "temperature": 0,
                "initial_prompt": initial_prompt,
                "verbose": False,
                "no_speech_threshold": 0.8,
                "logprob_threshold": -1.0,
                "compression_ratio_threshold": 2.4,
                "condition_on_previous_text": False,
                "language": language
            }
            
            if inference_lock:
                with inference_lock:
                    result = model.transcribe(audio, **transcribe_kwargs)
            else:
                result = model.transcribe(audio, **transcribe_kwargs)

            # 5. Segment Filtering (no_speech_prob < 0.2 & avg_logprob > -0.5)
            segments = [
                seg for seg in result["segments"] 
                if seg.get("no_speech_prob", 0) < 0.2 and seg.get("avg_logprob", -1.0) > -0.5
            ]
            raw_text = " ".join(seg["text"].strip() for seg in segments).strip()

            # 6. Hallucination Blacklist & Loop Detection
            import re
            cleaned = re.sub(r'[^\w\s]', '', raw_text.lower()).strip()
            
            # Common silence fallback hallucinations
            blacklist = ["thank you", "thanks for watching", "subtitle", "please subscribe", "the end"]
            if cleaned in blacklist:
                return ""

            words = cleaned.split()
            if len(words) >= 4:
                phrase_counts = {}
                for i in range(len(words)-1):
                    p = f"{words[i]} {words[i+1]}"
                    phrase_counts[p] = phrase_counts.get(p, 0) + 1
                if any(count > 2 for count in phrase_counts.values()):
                    return ""

            if len(raw_text) < 4:
                return ""
            
            return raw_text.strip()
        except Exception as e:
            print(f"⚠️  Safe transcription failed: {e}")
            return ""

    def _transcribe_raw_audio(self, audio: np.ndarray, model_name: str) -> str:
        """Legacy wrapper for unified safe transcription."""
        return self._safe_transcribe(model_name, audio)

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
            audio_duration_sec = audio.size / SAMPLE_RATE if SAMPLE_RATE > 0 else 0

            # For very short utterances, use full model for better whisper accuracy with minimal latency.
            if audio_duration_sec <= SHORT_UTTERANCE_FAST_PATH_SEC:
                raw_text = self._transcribe_raw_audio(audio, model_name)

            if fast_segments:
                raw_text = " ".join(segment for segment in fast_segments if segment).strip()
                safe_processed = min(max(fast_processed_samples, 0), audio.size)
                remaining = audio[safe_processed:]
                min_tail_samples = int(SAMPLE_RATE * FAST_COMMIT_MIN_TAIL_SEC)
                if remaining.size >= min_tail_samples:
                    # Use full model for tail to maximize accuracy on quiet speech.
                    tail_text = self._transcribe_raw_audio(remaining, model_name)
                    if tail_text:
                        raw_text = f"{raw_text} {tail_text}".strip()

            if not raw_text:
                # Fallback to full pass if chunk pipeline did not yield usable text.
                raw_text = self._transcribe_raw_audio(audio, model_name)

            # LLM layer ENABLED - hybrid approach
            app_name = self._app_monitor.get()
            
            # Optimization: Skip LLM cleanup for very short text (likely commands or single words)
            # This provides sub-second latency for common interactions.
            word_count = len(raw_text.split())
            if word_count < 3:
                cleaned_text, llm_ms = raw_text, 0
                print(f"⏩ Skipping LLM cleanup for short utterance ({word_count} words)")
            else:
                cleaned_text, llm_ms = clean(raw_text, app_name)  # ENABLED - advanced LLM cleanup
            
            # Phase 1 validation: print metrics
            print(f"Raw:     {raw_text}")
            print(f"Cleaned: {cleaned_text}")
            print(f"Hybrid (LLM + rule-based formatting): {llm_ms}ms")

            formatted = format_transcript(cleaned_text)

            if not formatted or len(formatted.strip()) < 4:
                from PyObjCTools import AppHelper
                AppHelper.callAfter(self._set_status, "No speech recognized")
                return

            self._last_processed_text = formatted
            RUNTIME_LAST_TEXT_PATH.write_text(formatted, encoding="utf-8")
            from PyObjCTools import AppHelper
            AppHelper.callAfter(self._set_last_preview, formatted)

            # Use new text injection system with failure detection
            app_name = self._app_monitor.get()
            if not app_name:
                print("⚠️  app detection failed, using default tone")
            
            success, reason = inject(formatted, app_name)
            
            if success:
                # Injection succeeded
                mode_hint = "chunked" if raw_text and fast_segments else "full"
                AppHelper.callAfter(self._set_status, f"Pasted via {model_name} ({mode_hint})")
                rumps.notification("Whisper Dictation", "Transcription inserted", formatted[:120])
            else:
                # Injection failed — show user-visible feedback
                AppHelper.callAfter(self._show_injection_failure, formatted, reason)

            # Save to history
            app_name = self._app_monitor.get()
            history_save(raw_text, formatted, app_name, llm_ms)
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Transcribe error: {exc}")

def main():
    app = WhisperMenuBarApp()
    if RUNTIME_LAST_TEXT_PATH.exists():
        try:
            app._last_processed_text = RUNTIME_LAST_TEXT_PATH.read_text(encoding="utf-8").strip()
            app._set_last_preview(app._last_processed_text)
        except Exception:  # noqa: BLE001
            pass
    app.run()


if __name__ == "__main__":
    main()
