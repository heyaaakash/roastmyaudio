"""
HUD overlay window shown during push-to-talk recording.

Displays a pill-shaped overlay at the bottom of the screen with
a live preview of transcribed text and a spinning indicator.
Only available when AppKit (PyObjC) is installed on macOS.
"""

try:
    from AppKit import (
        NSApp,
        NSBackingStoreBuffered,
        NSColor,
        NSEvent,
        NSMouseInRect,
        NSProgressIndicator,
        NSProgressIndicatorStyleSpinning,
        NSScreen,
        NSScreenSaverWindowLevel,
        NSTextField,
        NSWindow,
        NSWindowCollectionBehaviorFullScreenAuxiliary,
        NSWindowCollectionBehaviorMoveToActiveSpace,
        NSWindowStyleMaskBorderless,
    )
    from Foundation import NSMakeRect

    APPKIT_AVAILABLE = True
except Exception:
    APPKIT_AVAILABLE = False


class DictationOverlay:
    """
    Borderless pill-shaped overlay window shown at the bottom of the screen
    while the user is dictating. Shows live preview text and a spinner.

    Usage:
        overlay = DictationOverlay()   # build once at startup
        overlay.show()                 # call when recording starts
        overlay.set_preview_text("…")  # update live preview
        overlay.hide()                 # call when recording stops
    """

    PILL_WIDTH = 420
    PILL_HEIGHT = 112
    BOTTOM_MARGIN = 72

    def __init__(self):
        if not APPKIT_AVAILABLE:
            self.window = None
            return
        self.window = None
        self.title_label = None
        self.preview_label = None
        self.hint_label = None
        self.spinner = None
        self._build_window()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _make_label(self, text: str, frame):
        label = NSTextField.alloc().initWithFrame_(frame)
        label.setStringValue_(text)
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setEditable_(False)
        label.setSelectable_(False)
        label.setAlignment_(1)  # NSTextAlignmentCenter
        label.setTextColor_(NSColor.whiteColor())
        label.setFont_(None)
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
        self.title_label.setFrame_(NSMakeRect(58, h - 34, w - 70, 20))
        self.preview_label.setFrame_(NSMakeRect(58, 40, w - 70, 26))
        self.hint_label.setFrame_(NSMakeRect(58, 14, w - 70, 18))
        self.spinner.setFrame_(NSMakeRect(20, (h - 20) / 2, 20, 20))

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
        self.window.setBackgroundColor_(
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.06, 0.06, 0.08, 0.86)
        )
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
        content_view.layer().setCornerRadius_(self.PILL_HEIGHT / 2)
        content_view.layer().setMasksToBounds_(True)

        placeholder = NSMakeRect(0, 0, 300, 22)
        self.title_label = self._make_label("Dictating with Whisper", placeholder)
        self.preview_label = self._make_label("Listening...", placeholder)
        self.preview_label.setTextColor_(
            NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.95)
        )
        self.hint_label = self._make_label(
            "Release key to transcribe and paste", placeholder
        )
        self.hint_label.setTextColor_(
            NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.82)
        )
        self.spinner = NSProgressIndicator.alloc().initWithFrame_(
            NSMakeRect(0, 0, 20, 20)
        )
        self.spinner.setStyle_(NSProgressIndicatorStyleSpinning)
        self.spinner.setIndeterminate_(True)
        self.spinner.setDisplayedWhenStopped_(False)

        for view in (self.title_label, self.preview_label, self.hint_label, self.spinner):
            content_view.addSubview_(view)

        self._layout_content()
        self.window.orderOut_(None)

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
        self.preview_label.setStringValue_("Listening...")
        self.spinner.startAnimation_(None)
        self.window.orderFrontRegardless()

    def hide(self):
        """Hide the overlay."""
        if not self.window:
            return
        self.spinner.stopAnimation_(None)
        self.window.orderOut_(None)

    def set_preview_text(self, text: str):
        """Update the live preview label."""
        if not self.preview_label:
            return
        value = (text or "").strip() or "Listening..."
        self.preview_label.setStringValue_(value)
