"""
Audio capture utilities for the macOS menu bar app.

Wraps sounddevice stream management and provides helpers for
device enumeration and audio normalization.
"""

from typing import Callable, Optional

import numpy as np
import sounddevice as sd

# Audio constants — must match Whisper's expected input format
SAMPLE_RATE = 16_000   # Hz — Whisper native sample rate
CHANNELS = 1           # Mono
DTYPE = "float32"
AUDIO_NORM_TARGET_RMS = 0.15   # Target RMS after normalization
AUDIO_NORM_MAX_SCALE = 2.0     # Never boost more than 2x


# ---------------------------------------------------------------------------
# Device helpers
# ---------------------------------------------------------------------------
def list_input_devices() -> list[tuple[int, str]]:
    """
    Return a list of (device_id, name) tuples for all available input devices.
    """
    devices = []
    try:
        for idx, device in enumerate(sd.query_devices()):
            if int(device.get("max_input_channels", 0) or 0) > 0:
                name = str(device.get("name") or f"Input {idx}")
                devices.append((idx, name))
    except Exception:
        pass
    return devices


def get_default_input_device() -> Optional[int]:
    """Return the system default input device ID, or None."""
    try:
        default_input, _ = sd.default.device
        if default_input is not None and default_input >= 0:
            return int(default_input)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Audio normalization
# ---------------------------------------------------------------------------
def normalize_audio(audio: np.ndarray) -> np.ndarray:
    """
    Boost quiet speech to a standard loudness level for better Whisper accuracy.

    - Computes RMS of the signal.
    - Scales so RMS reaches AUDIO_NORM_TARGET_RMS, capped at AUDIO_NORM_MAX_SCALE.
    - Clips output to [-1, 1] to prevent clipping artifacts.
    """
    if audio.size == 0:
        return audio
    rms = float(np.sqrt(np.mean(audio ** 2)))
    if rms < 0.001:
        return audio  # Near-silent — leave as-is to avoid amplifying pure noise
    scale = min(AUDIO_NORM_TARGET_RMS / rms, AUDIO_NORM_MAX_SCALE)
    return np.clip(audio * scale, -1.0, 1.0).astype(np.float32)


# ---------------------------------------------------------------------------
# Stream management
# ---------------------------------------------------------------------------
class AudioRecorder:
    """
    Simple non-blocking sounddevice stream wrapper.

    Usage:
        recorder = AudioRecorder(device_id=None)
        recorder.start()
        # ... user speaks ...
        audio = recorder.stop()  # returns concatenated float32 array
    """

    def __init__(self, device_id: Optional[int] = None):
        self.device_id = device_id
        self._chunks: list[np.ndarray] = []
        self._stream: Optional[sd.InputStream] = None

    # ------------------------------------------------------------------
    def _callback(self, indata: np.ndarray, frames: int, time_info, status):
        """Non-blocking callback — append a copy of each audio chunk."""
        if status:
            return
        self._chunks.append(indata.copy())

    # ------------------------------------------------------------------
    def start(self, extra_callback: Optional[Callable] = None):
        """
        Open and start the audio stream.

        Args:
            extra_callback: Optional callable(chunk: np.ndarray) called for
                            each audio chunk in addition to buffering it.
        """
        self._chunks = []

        def _cb(indata, frames, time_info, status):
            self._callback(indata, frames, time_info, status)
            if extra_callback and not status:
                extra_callback(indata.copy().reshape(-1))

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            device=self.device_id,
            callback=_cb,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        """
        Stop the stream and return all captured audio as a flat float32 array.
        """
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        if not self._chunks:
            return np.zeros(0, dtype=np.float32)

        audio = np.concatenate(self._chunks, axis=0).reshape(-1)
        self._chunks = []
        return audio
