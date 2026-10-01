"""
HUD overlay window shown during push-to-talk recording.

A world-class, glassmorphic liquid "pill" overlay inspired by Apple Intelligence & macOS Sequoia:

  * Translucent NSVisualEffectView with dark HUD vibrancy and pill geometry
  * Sound-reactive 5-bar gradient visualizer (Cyan-to-Violet Siri/Gemini glow) with fluid physics & idle breathing
  * Live streaming ghost text preview with zero-flicker CATransition cross-fades
  * Context mode badge indicator ([Code], [Chat], [Email], [Hands-Free])
  * Apple trackpad haptic micro-ticks & audio feedback cues on start / stop
  * Click-through borderless window that floats above all spaces without stealing focus

Only available when AppKit (PyObjC) is installed on macOS.
"""

from __future__ import annotations

import math
import random

try:
    import objc
    from AppKit import (
        NSAnimationContext,
        NSBackingStoreBuffered,
        NSColor,
        NSEvent,
        NSFont,
        NSMouseInRect,
        NSPanel,
        NSScreen,
        NSSound,
        NSStatusWindowLevel,
        NSTextField,
        NSView,
        NSVisualEffectView,
        NSWindowCollectionBehaviorCanJoinAllSpaces,
        NSWindowCollectionBehaviorFullScreenAuxiliary,
        NSWindowCollectionBehaviorStationary,
        NSWindowStyleMaskBorderless,
        NSWindowStyleMaskNonactivatingPanel,
    )
    from Foundation import (
        NSMakeRect,
        NSRunLoop,
        NSRunLoopCommonModes,
        NSTimer,
    )
    from Quartz import (
        CAGradientLayer,
        CATransaction,
        CATransition,
    )

    APPKIT_AVAILABLE = True
except Exception:
    APPKIT_AVAILABLE = False


# Optional Haptics
try:
    from AppKit import (
        NSHapticFeedbackManager,
        NSHapticFeedbackPatternGeneric,
        NSHapticFeedbackPerformanceTimeNow,
    )

    HAPTICS_AVAILABLE = True
except Exception:
    HAPTICS_AVAILABLE = False


def trigger_haptic():
    """Trigger a subtle haptic feedback pulse on macOS trackpad."""
    if not HAPTICS_AVAILABLE:
        return
    try:
        performer = NSHapticFeedbackManager.defaultPerformer()
        if performer is not None:
            performer.performFeedbackPattern_performanceTime_(
                NSHapticFeedbackPatternGeneric,
                NSHapticFeedbackPerformanceTimeNow,
            )
    except Exception:
        pass


# Visual-effect material / blending / state enums (kept as ints for ABI safety).
_MATERIAL_HUD = 13
_BLENDING_BEHIND_WINDOW = 0
_VIBRANCY_ACTIVE = 1

# Waveform visualizer geometry & dynamics (pure-Python, testable).
WAVEFORM_BAR_COUNT = 14
WAVEFORM_BAR_WIDTH = 3.5
WAVEFORM_BAR_GAP = 3.0
WAVEFORM_BAR_MIN_H = 3.5
WAVEFORM_TICK_FPS = 60.0
WAVEFORM_SMOOTHING = 0.55
WAVEFORM_DECAY = 0.85

# RMS (float32 amplitude, 0..1) at which the meter is considered "full".
_AUDIO_LEVEL_FULL_RMS = 0.08


# ---------------------------------------------------------------------------
# Pure-Python helpers (importable & testable without AppKit)
# ---------------------------------------------------------------------------
def _normalize_audio_level(rms: float) -> float:
    """
    Map a raw audio RMS value (float32 amplitude, ~0..1) to a 0..1 display level.

    Quiet speech (~0.005) maps to ~0.25, normal speech (~0.02) to ~0.5,
    loud speech (~0.08+) saturates to 1.0. A square-root curve gives the
    bars a lively, non-linear response.
    """
    if rms <= 0.0:
        return 0.0
    norm = rms / _AUDIO_LEVEL_FULL_RMS
    if norm >= 1.0:
        return 1.0
    return norm**0.5


def _bar_x_positions(count: int, width: float, gap: float, container_width: float) -> list[float]:
    """Evenly-spaced bar origins so the group is horizontally centered."""
    total = count * width + (count - 1) * gap
    start = (container_width - total) / 2.0
    return [start + i * (width + gap) for i in range(count)]


if APPKIT_AVAILABLE:

    class _WaveformView(NSView):
        """Hosts 14 vibrant multi-frequency gradient CALayer bars with hyper-fluid sound-reactive physics."""

        def initWithFrame_(self, frame):
            self = objc.super(_WaveformView, self).initWithFrame_(frame)
            if self is None:
                return None
            self.setWantsLayer_(True)
            self._target_level = 0.0
            self._displayed = 0.0
            self._tick_count = 0
            self._timer = None
            self._make_bars()
            return self

        # -- layout / lifecycle ------------------------------------------------
        @objc.python_method
        def _make_bars(self):
            root = self.layer()
            root.setBackgroundColor_(NSColor.clearColor().CGColor)
            self._bars = []

            # Dynamic Siri / Gemini multi-stop aurora palette
            c1 = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.02, 0.71, 0.95, 0.98
            ).CGColor  # Electric Cyan
            c2 = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.55, 0.27, 0.97, 0.98
            ).CGColor  # Neon Violet
            c3 = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                0.96, 0.25, 0.52, 0.98
            ).CGColor  # Hot Pink / Coral

            for i in range(WAVEFORM_BAR_COUNT):
                bar = CAGradientLayer.layer()
                # Shift gradient stops per bar across the spectrum
                if i < WAVEFORM_BAR_COUNT // 2:
                    bar.setColors_([c1, c2])
                else:
                    bar.setColors_([c2, c3])
                bar.setStartPoint_((0.5, 0.0))
                bar.setEndPoint_((0.5, 1.0))
                bar.setCornerRadius_(WAVEFORM_BAR_WIDTH / 2.0)
                bar.setMasksToBounds_(True)
                bar.setOpacity_(0.95)
                root.addSublayer_(bar)
                self._bars.append(bar)
            self._layout_bars()

        def layout(self):
            objc.super(_WaveformView, self).layout()
            self._layout_bars()

        @objc.python_method
        def _layout_bars(self):
            bounds = self.bounds()
            W = bounds.size.width
            xs = _bar_x_positions(WAVEFORM_BAR_COUNT, WAVEFORM_BAR_WIDTH, WAVEFORM_BAR_GAP, W)
            CATransaction.begin()
            CATransaction.setValue_forKey_(True, "disableActions")
            for i, bar in enumerate(self._bars):
                bar.setFrame_(NSMakeRect(xs[i], 0.0, WAVEFORM_BAR_WIDTH, WAVEFORM_BAR_MIN_H))
            CATransaction.commit()

        # -- animation loop -----------------------------------------------------
        @objc.python_method
        def _start_timer(self):
            if self._timer is not None:
                return
            self._timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                1.0 / WAVEFORM_TICK_FPS, self, "tick:", None, True
            )
            NSRunLoop.currentRunLoop().addTimer_forMode_(self._timer, NSRunLoopCommonModes)

        @objc.python_method
        def _stop_timer(self):
            if self._timer is not None:
                self._timer.invalidate()
                self._timer = None

        @objc.python_method
        def resume_animation(self):
            self._start_timer()

        @objc.python_method
        def pause_animation(self):
            self._stop_timer()
            self._target_level = 0.0
            self._displayed = 0.0
            self._layout_bars()

        @objc.python_method
        def reset(self):
            self._target_level = 0.0
            self._displayed = 0.0
            self._tick_count = 0
            self._layout_bars()

        def tick_(self, sender):
            self._tick_count += 1
            self._displayed += (self._target_level - self._displayed) * WAVEFORM_SMOOTHING
            if self._target_level < 0.0009:
                self._displayed *= WAVEFORM_DECAY

            bounds = self.bounds()
            W = bounds.size.width
            H = bounds.size.height
            xs = _bar_x_positions(WAVEFORM_BAR_COUNT, WAVEFORM_BAR_WIDTH, WAVEFORM_BAR_GAP, W)

            # High-energy multi-harmonic traveling waves
            t = self._tick_count * 0.18
            CATransaction.begin()
            CATransaction.setValue_forKey_(True, "disableActions")

            for i, bar in enumerate(self._bars):
                # Frequency harmonics across 14 bars
                norm_pos = (i + 0.5) / WAVEFORM_BAR_COUNT
                weight = math.sin(norm_pos * math.pi)

                freq1 = math.sin(t * 2.2 + i * 0.62)
                freq2 = math.cos(t * 3.1 - i * 0.48)
                freq3 = math.sin(t * 1.2 + i * 1.15)
                wave_harmonic = 0.45 * freq1 + 0.35 * freq2 + 0.20 * freq3

                if self._displayed > 0.015:
                    # CRAZY sound-reactive voice animation: explosive peaks + dancing harmonic ripples
                    jitter = random.uniform(-0.18, 0.18) * self._displayed
                    voice_energy = self._displayed * (0.60 + 0.40 * weight)
                    amp = voice_energy * (0.85 + 0.55 * wave_harmonic) + jitter
                    amp = max(0.08, min(1.0, amp))
                else:
                    # Mesmerizing idle breathing wave ripple
                    amp = 0.07 + 0.06 * (0.5 + 0.5 * wave_harmonic) * (0.4 + 0.6 * weight)

                h = max(WAVEFORM_BAR_MIN_H, min(H, amp * H))
                y = (H - h) / 2.0
                bar.setFrame_(NSMakeRect(xs[i], y, WAVEFORM_BAR_WIDTH, h))
            CATransaction.commit()

        # -- level API ---------------------------------------------------------
        @objc.python_method
        def set_level(self, level: float):
            self._target_level = max(0.0, min(1.0, float(level)))

        def dealloc(self):
            self._stop_timer()
            objc.super(_WaveformView, self).dealloc()

else:
    _WaveformView = None


# ---------------------------------------------------------------------------
# Public overlay window
# ---------------------------------------------------------------------------
class DictationOverlay:
    """
    World-class borderless glass pill shown while the user is dictating.

    Usage:
        overlay = DictationOverlay()          # build once at startup
        overlay.show()                        # call when recording starts
        overlay.set_title("Dictating · base") # optional caption
        overlay.set_mode_badge("Code")        # optional context badge
        overlay.set_preview_text("...")       # update live preview (ghost text)
        overlay.set_audio_level(0.6)          # update waveform (0..1)
        overlay.hide()                        # call when recording stops
    """

    PILL_WIDTH = 540
    PILL_HEIGHT = 80
    BOTTOM_MARGIN = 84

    WAVEFORM_W = 96
    WAVEFORM_X = 22
    TEXT_X = 132
    TEXT_W_INSET = 148

    def __init__(self):
        self.window = None
        self._visual_effect = None
        self._waveform = None
        self._title_label = None
        self._preview_label = None
        self._cue_start = None
        self._cue_stop = None
        self._current_mode = ""
        self._base_title = "Dictating"
        if not APPKIT_AVAILABLE:
            return
        self._build_window()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _make_label(self, text: str, font, color) -> NSTextField:
        label = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 1, 1))
        label.setStringValue_(text)
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setEditable_(False)
        label.setSelectable_(False)
        label.setAlignment_(0)  # NSTextAlignmentLeft
        label.setWantsLayer_(True)
        label.setFont_(font)
        label.setTextColor_(color)
        return label

    def _pill_frame_for_screen(self, screen_or_frame):
        if hasattr(screen_or_frame, "visibleFrame"):
            visible = screen_or_frame.visibleFrame()
        elif hasattr(screen_or_frame, "origin"):
            visible = screen_or_frame
        else:
            visible = NSScreen.mainScreen().visibleFrame()
        x = visible.origin.x + (visible.size.width - self.PILL_WIDTH) / 2.0
        y = visible.origin.y + 130.0
        return NSMakeRect(x, y, self.PILL_WIDTH, self.PILL_HEIGHT)

    def _screen_for_current_pointer(self):
        mouse_point = NSEvent.mouseLocation()
        for screen in NSScreen.screens():
            if NSMouseInRect(mouse_point, screen.frame(), False):
                return screen
        return NSScreen.mainScreen()

    def _layout_content(self):
        w, h = self.PILL_WIDTH, self.PILL_HEIGHT
        if self._waveform is not None:
            self._waveform.setFrame_(NSMakeRect(self.WAVEFORM_X, 14, self.WAVEFORM_W, h - 28))
        if self._title_label is not None:
            self._title_label.setFrame_(NSMakeRect(self.TEXT_X, h - 28, w - self.TEXT_W_INSET, 16))
        if self._preview_label is not None:
            self._preview_label.setFrame_(
                NSMakeRect(self.TEXT_X, 12, w - self.TEXT_W_INSET, h - 42)
            )

    def _build_window(self):
        screen = NSScreen.mainScreen()
        frame = self._pill_frame_for_screen(screen)

        self.window = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            frame,
            NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
            NSBackingStoreBuffered,
            False,
        )
        self.window.setFloatingPanel_(True)
        self.window.setBecomesKeyOnlyIfNeeded_(True)
        self.window.setReleasedWhenClosed_(False)
        self.window.setOpaque_(False)
        self.window.setBackgroundColor_(NSColor.clearColor())
        self.window.setAlphaValue_(1.0)
        self.window.setIgnoresMouseEvents_(True)
        self.window.setLevel_(NSStatusWindowLevel)
        self.window.setHasShadow_(True)
        self.window.setHidesOnDeactivate_(False)
        self.window.setCanHide_(False)
        self.window.setMovable_(False)
        self.window.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
            | NSWindowCollectionBehaviorStationary
        )

        # Liquid Frosted Glass Effect View
        ve = NSVisualEffectView.alloc().initWithFrame_(
            NSMakeRect(0, 0, self.PILL_WIDTH, self.PILL_HEIGHT)
        )
        ve.setBlendingMode_(1)  # NSVisualEffectBlendingModeWithinWindow
        ve.setMaterial_(2)  # NSVisualEffectMaterialDark
        ve.setState_(1)  # NSVisualEffectStateActive
        ve.setWantsLayer_(True)

        # Pill Corner Geometry & Specular Border Rim
        ve.layer().setCornerRadius_(self.PILL_HEIGHT / 2.0)
        ve.layer().setMasksToBounds_(True)
        ve.layer().setBorderWidth_(1.5)
        ve.layer().setBorderColor_(NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.25).CGColor)
        ve.layer().setBackgroundColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.10, 0.11, 0.14, 0.96).CGColor
        )
        self._visual_effect = ve
        self.window.setContentView_(ve)

        # Modern SF Pro Typography
        self._title_label = self._make_label(
            "●  DICTATING",
            NSFont.boldSystemFontOfSize_(10.5),
            NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.60),
        )
        self._preview_label = self._make_label(
            "Listening...",
            NSFont.systemFontOfSize_(15.5),
            NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.98),
        )
        ve.addSubview_(self._title_label)
        ve.addSubview_(self._preview_label)

        self._waveform = _WaveformView.alloc().initWithFrame_(
            NSMakeRect(self.WAVEFORM_X, 14, self.WAVEFORM_W, self.PILL_HEIGHT - 28)
        )
        ve.addSubview_(self._waveform)

        # Audio Micro-Cue Feedback
        self._cue_start = NSSound.soundNamed_("Tink")
        if self._cue_start is not None:
            self._cue_start.setVolume_(0.28)
        self._cue_stop = NSSound.soundNamed_("Pop")
        if self._cue_stop is not None:
            self._cue_stop.setVolume_(0.25)

        self._layout_content()
        self.window.orderOut_(None)

    def _animate_alpha(self, target: float, duration: float, completion=None):
        if not self.window:
            return
        NSAnimationContext.beginGrouping()
        ctx = NSAnimationContext.currentContext()
        ctx.setDuration_(duration)
        if completion is not None:
            ctx.setCompletionHandler_(completion)
        self.window.animator().setAlphaValue_(target)
        NSAnimationContext.endGrouping()

    def _play_cue(self, sound):
        if sound is None:
            return
        try:
            sound.play()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def show(self, feedback=True):
        """Show the overlay on the screen containing the mouse pointer."""
        if not self.window:
            return
        from AppKit import NSWorkspace

        self._reduce_motion = NSWorkspace.sharedWorkspace().accessibilityDisplayShouldReduceMotion()
        screen = self._screen_for_current_pointer()
        frame = self._pill_frame_for_screen(screen)
        self.window.setFrame_display_(frame, True)
        self._layout_content()
        if self._waveform is not None:
            self._waveform.reset()
            if not self._reduce_motion:
                self._waveform.resume_animation()
        self.set_preview_text("Listening...")
        self.window.setAlphaValue_(1.0)
        self.window.orderFrontRegardless()
        if feedback:
            self._play_cue(self._cue_start)
            trigger_haptic()

    def hide(self, feedback=True):
        """Fade the overlay out and remove it from screen with haptic release."""
        if not self.window:
            return
        if self._waveform is not None:
            self._waveform.pause_animation()
        if feedback:
            self._play_cue(self._cue_stop)
            trigger_haptic()
        self._animate_alpha(0.0, 0.14, self._order_out)

    def _order_out(self):
        if self.window is not None:
            self.window.orderOut_(None)

    def set_title(self, text: str, mode: str | None = None):
        """Update the small caption with model info and context mode pill."""
        if not self._title_label:
            return
        self._base_title = (text or "").strip() or "Dictating"
        if mode:
            self._current_mode = mode

        # Apple-styled status row with dot indicator and badges
        if self._current_mode:
            display_text = f"●  {self._base_title.upper()}  ·  [{self._current_mode.upper()}]"
        else:
            display_text = f"●  {self._base_title.upper()}"

        self._title_label.setStringValue_(display_text)

    def set_mode_badge(self, mode: str):
        """Update the mode badge (e.g. Code, Chat, Email, Hands-Free)."""
        self._current_mode = (mode or "").strip()
        self.set_title(self._base_title)

    def set_preview_text(self, text: str):
        """Update the live preview label with a smooth zero-flicker cross-fade."""
        if not self._preview_label:
            return
        value = (text or "").strip() or "Listening..."
        layer = self._preview_label.layer()
        if layer is not None:
            fade = CATransition.animation()
            fade.setType_("fade")
            fade.setDuration_(0.10)
            layer.addAnimation_forKey_(fade, "ghostFade")
        self._preview_label.setStringValue_(value)

    def set_audio_level(self, level: float):
        """Drive the waveform visualizer from a normalized 0..1 level."""
        if self._waveform is None:
            return
        self._waveform.set_level(level)

    def reset_waveform(self):
        """Reset the waveform to idle (flat bars, keep animating)."""
        if self._waveform is None:
            return
        self._waveform.reset()
