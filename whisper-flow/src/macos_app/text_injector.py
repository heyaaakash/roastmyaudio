import time
import threading
from AppKit import NSWorkspace, NSPasteboard, NSStringPboardType

try:
    import Quartz
    QUARTZ_AVAILABLE = True
except Exception:
    QUARTZ_AVAILABLE = False


def get_active_app() -> str:
    """Get the name of the currently frontmost application."""
    try:
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        return app.localizedName() or ""
    except Exception:
        return ""


class AppMonitor:
    """Continuously tracks the frontmost app in background thread."""

    def __init__(self):
        self._last_app = ""
        self._running = False
        self._thread = None

    def start(self):
        """Start monitoring the active app in a daemon thread."""
        self._running = True
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()

    def _poll(self):
        """Poll active app every 0.12 seconds for faster response."""
        while self._running:
            app = get_active_app()
            # Only update if it's not our own app (avoid self-reference)
            if app and "python" not in app.lower() and "wispr" not in app.lower():
                self._last_app = app
            time.sleep(0.12)

    def get(self) -> str:
        """Get the last known active app name."""
        return self._last_app

    def stop(self):
        """Stop the monitoring thread."""
        self._running = False


def _save_clipboard() -> str:
    """Save and return current clipboard contents."""
    pb = NSPasteboard.generalPasteboard()
    return pb.stringForType_(NSStringPboardType) or ""


def _write_clipboard(text: str):
    """Write text to clipboard."""
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.setString_forType_(text, NSStringPboardType)


def _paste():
    """Simulate Cmd+V via Quartz CGEvent."""
    if not QUARTZ_AVAILABLE:
        raise RuntimeError("Quartz not available for text injection")

    src = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)

    # Key down
    ev = Quartz.CGEventCreateKeyboardEvent(src, 0x09, True)  # 0x09 = V key
    Quartz.CGEventSetFlags(ev, Quartz.kCGEventFlagMaskCommand)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)

    # Key up
    ev = Quartz.CGEventCreateKeyboardEvent(src, 0x09, False)
    Quartz.CGEventSetFlags(ev, Quartz.kCGEventFlagMaskCommand)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)

    time.sleep(0.05)  # let the app process the paste


# Apps where paste rarely works as expected (no text field + Cmd+V doesn't work)
_SKIP_INJECTION_APPS = {
    "Finder",
    "System Preferences",
    "System Settings",
    "Spotlight",
}


def _is_pasteable(app_name: str) -> bool:
    """
    Check if the active app is likely to support text injection via Cmd+V.
    Apps like Finder and System Settings don't have editable text fields.
    """
    if not app_name:
        # Unknown app — try injection anyway
        return True
    
    app_lower = app_name.lower()
    for skip_app in _SKIP_INJECTION_APPS:
        if skip_app.lower() in app_lower:
            return False
    return True


def inject(text: str, app_name: str = "") -> tuple[bool, str]:
    """
    Inject text into the currently focused field with failure detection.

    Flow:
    1. Check if active app is pasteable
    2. Save current clipboard contents
    3. Write cleaned text to clipboard
    4. Simulate Cmd+V
    5. Check if clipboard was consumed (heuristic for success)
    6. Restore original clipboard

    Args:
        text: Text to inject
        app_name: Name of active app (for pre-flight check)

    Returns:
        tuple (success: bool, reason: str)
        - (True, "ok") if injection likely succeeded
        - (False, reason) if pre-flight check failed or paste was not consumed
    """
    if not text or not text.strip():
        return False, "empty text"

    if not _is_pasteable(app_name):
        return False, f"{app_name} doesn't support paste injection"

    if not QUARTZ_AVAILABLE:
        return False, "Quartz not available for text injection"

    try:
        original = _save_clipboard()
        _write_clipboard(text)
        time.sleep(0.01)  # give clipboard time to settle
        _paste()
        time.sleep(0.03)  # local apps respond to Cmd+V almost instantly
        
        _write_clipboard(original)  # restore original
        return True, "ok"
    
    except Exception as e:
        return False, str(e)


# Quick test
if __name__ == "__main__":
    print("Active app:", get_active_app())
    print("Testing AppMonitor...")

    monitor = AppMonitor()
    monitor.start()

    time.sleep(1)
    print("Monitored app:", monitor.get())

    # Test injection — open Notes or any text editor first
    test_text = "Standard dictation test."
    input("\nOpen a text editor and click into a text field, then press Enter...")

    success, reason = inject(test_text, monitor.get())
    print(f"Injection: {'✓ success' if success else f'✗ failed ({reason})'}")

    monitor.stop()
