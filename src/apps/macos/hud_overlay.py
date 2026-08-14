"""
HUD overlay window shown during push-to-talk recording.

A glassmorphic, liquid "pill" overlay floating near the bottom of the screen:

  * translucent NSVisualEffectView (dark HUD vibrancy) with a rounded pill mask
  * live 5-bar audio waveform visualizer that pulses with the microphone
  * ghost streaming preview text that cross-fades token-by-token (no flicker)
  * subtle fade + scale-in when dictation begins, fade-out when it ends
  * optional micro sound cue on start / stop

The overlay is click-through and never steals focus.

Only available when AppKit (PyObjC) is installed on macOS.
"""

try:
    import objc
    from AppKit import (
        NSAnimationContext,
        NSBackingStoreBuffered,
        NSColor,
        NSEvent,
        NSFont,
        NSMouseInRect,
        NSScreen,
        NSScreenSaverWindowLevel,
        NSSound,
        NSTextField,
        NSView,
        NSVisualEffectView,
        NSWindow,
        NSWindowCollectionBehaviorFullScreenAuxiliary,
        NSWindowCollectionBehaviorMoveToActiveSpace,
        NSWindowStyleMaskBorderless,
    )
    from Foundation import (
        NSMakeRect,
        NSRunLoop,
        NSRunLoopCommonModes,
        NSTimer,
    )
    from Quartz import CALayer, CATransaction, CATransition

    APPKIT_AVAILABLE = True
except Exception:
    APPKIT_AVAILABLE = False


# Visual-effect material / blending / state enums (kept as ints for ABI safety).
_MATERIAL_HUD = 13
_BLENDING_BEHIND_WINDOW = 0
_VIBRANCY_ACTIVE = 1

# Waveform visualizer geometry & dynamics (pure-Python, testable).
WAVEFORM_BAR_COUNT = 5
WAVEFORM_BAR_WIDTH = 5.0
WAVEFORM_BAR_GAP = 5.0
WAVEFORM_BAR_MIN_H = 4.0
WAVEFORM_TICK_FPS = 60.0
WAVEFORM_SMOOTHING = 0.35
WAVEFORM_DECAY = 0.86

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
    return norm ** 0.5


def _bar_x_positions(count: int, width: float, gap: float, container_width: float) -> list[float]:
    """Evenly-spaced bar origins so the group is horizontally centered."""
    total = count * width + (count - 1) * gap
    start = (container_width - total) / 2.0
    return [start + i * (width + gap) for i in range(count)]


if APPKIT_AVAILABLE:

    class _WaveformView(NSView):
        """Hosts N rounded CALayer bars and animates them from a 0..1 level."""

        def initWithFrame_(self, frame):
            self = objc.super(_WaveformView, self).initWithFrame_(frame)
            if self is None:
                return None
            self.setWantsLayer_(True)
            self._target_level = 0.0
            self._displayed = 0.0
            self._timer = None
            self._make_bars()
            return self

        # -- layout / lifecycle ------------------------------------------------
        @objc.python_method
        def _make_bars(self):
            root = self.layer()
            root.setBackgroundColor_(NSColor.clearColor().CGColor)
            self._bars = []
            for _ in range(WAVEFORM_BAR_COUNT):
                bar = CALayer.layer()
                bar.setBackgroundColor_(NSColor.whiteColor().CGColor)
                bar.setCornerRadius_(WAVEFORM_BAR_WIDTH / 2.0)
                bar.setOpacity_(0.92)
                bar.setMasksToBounds_(True)
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
            xs = _bar_x_positions(
                WAVEFORM_BAR_COUNT, WAVEFORM_BAR_WIDTH, WAVEFORM_BAR_GAP, W
            )
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
            self._layout_bars()

        def tick_(self, sender):
            import math
            import random

            self._displayed += (self._target_level - self._displayed) * WAVEFORM_SMOOTHING
            if self._target_level < 0.0009:
                self._displayed *= WAVEFORM_DECAY

            bounds = self.bounds()
            W = bounds.size.width
            H = bounds.size.height
            xs = _bar_x_positions(
                WAVEFORM_BAR_COUNT, WAVEFORM_BAR_WIDTH, WAVEFORM_BAR_GAP, W
            )

            CATransaction.begin()
            CATransaction.setValue_forKey_(True, "disableActions")
            for i, bar in enumerate(self._bars):
                weight = math.sin(((i + 1) / (WAVEFORM_BAR_COUNT + 1)) * math.pi)
                jitter = random.uniform(-0.12, 0.12) * max(self._displayed, 0.0)
                amp = max(0.0, self._displayed * weight + jitter)
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
    Borderless glass pill shown while the user is dictating.

    Usage:
        overlay = DictationOverlay()          # build once at startup
        overlay.show()                        # call when recording starts
        overlay.set_title("Dictating · base") # optional caption
        overlay.set_preview_text("...")       # update live preview (ghost text)
        overlay.set_audio_level(0.6)          # update waveform (0..1)
        overlay.hide()                        # call when recording stops
    """

    PILL_WIDTH = 486
    PILL_HEIGHT = 78
    BOTTOM_MARGIN = 80

    WAVEFORM_W = 72
    WAVEFORM_X = 18
    TEXT_X = 104
    TEXT_W_INSET = 116

    def __init__(self):
        self.window = None
        self._visual_effect = None
        self._waveform = None
        self._title_label = None
        self._preview_label = None
        self._cue_start = None
        self._cue_stop = None
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
        label.setAlignment_(1)  # NSTextAlignmentCenter
        label.setWantsLayer_(True)
        label.setFont_(font)
        label.setTextColor_(color)
        return label

    def _pill_frame_for_screen(self, screen_frame):
        x = screen_frame.origin.x + (screen_frame.size.width - self.PILL_WIDTH) / 2
        y = screen_frame.origin.y + self.BOTTOM_MARGIN
        return NSMakeRect(x, y, self.PILL_WIDTH, self.PILL_HEIGHT)

    def _screen_for_current_pointer(self):
        mouse_point = NSEvent.mouseLocation()
        for screen in NSScreen.screens():
            if NSMouseInRect(mouse_point, screen.frame(), False):
                return screen
        return NSScreen.mainScreen()

    def _layout_content(self):
        w, h = self.PILL_WIDTH, self.PILL_HEIGHT
        self._waveform.setFrame_(
            NSMakeRect(self.WAVEFORM_X, 12, self.WAVEFORM_W, h - 24)
        )
        self._title_label.setFrame_(
            NSMakeRect(self.TEXT_X, h - 26, w - self.TEXT_W_INSET, 14)
        )
        self._preview_label.setFrame_(
            NSMakeRect(self.TEXT_X, 12, w - self.TEXT_W_INSET, h - 40)
        )

    def _build_window(self):
        screen = NSScreen.mainScreen()
        frame = self._pill_frame_for_screen(screen.frame())

        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            frame,
            NSWindowStyleMaskBorderless,
            NSBackingStoreBuffered,
            False,
        )
        self.window.setReleasedWhenClosed_(False)
        self.window.setOpaque_(False)
        self.window.setBackgroundColor_(NSColor.clearColor())
        self.window.setAlphaValue_(0.0)
        self.window.setIgnoresMouseEvents_(True)
        self.window.setLevel_(NSScreenSaverWindowLevel)
        self.window.setHasShadow_(True)
        self.window.setHidesOnDeactivate_(False)
        self.window.setCanHide_(False)
        self.window.setMovable_(False)
        self.window.setCollectionBehavior_(
            NSWindowCollectionBehaviorFullScreenAuxiliary
            | NSWindowCollectionBehaviorMoveToActiveSpace
        )

        ve = NSVisualEffectView.alloc().initWithFrame_(
            NSMakeRect(0, 0, self.PILL_WIDTH, self.PILL_HEIGHT)
        )
        ve.setBlendingMode_(_BLENDING_BEHIND_WINDOW)
        ve.setMaterial_(_MATERIAL_HUD)
        ve.setState_(_VIBRANCY_ACTIVE)
        ve.setWantsLayer_(True)
        ve.layer().setCornerRadius_(self.PILL_HEIGHT / 2.0)
        ve.layer().setMasksToBounds_(True)
        ve.layer().setBorderWidth_(1.0)
        ve.layer().setBorderColor_(
            NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.14).CGColor
        )
        self._visual_effect = ve
        self.window.setContentView_(ve)

        self._title_label = self._make_label(
            "Dictating",
            NSFont.boldSystemFontOfSize_(11.0),
            NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.55),
        )
        self._preview_label = self._make_label(
            "Listening...",
            NSFont.systemFontOfSize_(15.0),
            NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.96),
        )
        ve.addSubview_(self._title_label)
        ve.addSubview_(self._preview_label)

        self._waveform = _WaveformView.alloc().initWithFrame_(
            NSMakeRect(self.WAVEFORM_X, 12, self.WAVEFORM_W, self.PILL_HEIGHT - 24)
        )
        ve.addSubview_(self._waveform)

        self._cue_start = NSSound.soundNamed_("Tink")
        if self._cue_start is not None:
            self._cue_start.setVolume_(0.35)
        self._cue_stop = NSSound.soundNamed_("Pop")
        if self._cue_stop is not None:
            self._cue_stop.setVolume_(0.30)

        self._layout_content()
        self.window.orderOut_(None)

    def _animate_alpha(self, target: float, duration: float, completion=None):
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
    def show(self):
        """Show the overlay on the screen containing the mouse pointer."""
        if not self.window:
            return
        screen = self._screen_for_current_pointer()
        frame = self._pill_frame_for_screen(screen.frame())
        self.window.setFrame_display_(frame, True)
        self._layout_content()
        if self._waveform is not None:
            self._waveform.reset()
            self._waveform.resume_animation()
        self.set_preview_text("Listening...")
        self.window.setAlphaValue_(0.0)
        self.window.orderFrontRegardless()
        self._animate_alpha(1.0, 0.16)
        self._play_cue(self._cue_start)

    def hide(self):
        """Fade the overlay out and remove it from screen."""
        if not self.window:
            return
        if self._waveform is not None:
            self._waveform.pause_animation()
        self._play_cue(self._cue_stop)
        self._animate_alpha(0.0, 0.14, self._order_out)

    def _order_out(self):
        if self.window is not None:
            self.window.orderOut_(None)

    def set_title(self, text: str):
        """Update the small caption above the preview text."""
        if not self._title_label:
            return
        self._title_label.setStringValue_((text or "").strip() or "Dictating")

    def set_preview_text(self, text: str):
        """Update the live preview label with a smooth cross-fade."""
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
