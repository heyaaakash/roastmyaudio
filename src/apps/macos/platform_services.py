"""Permission, target, login-item and diagnostics helpers with explicit user actions."""

import json
import platform
import sys
from pathlib import Path


def permissions():
    from ApplicationServices import AXIsProcessTrusted
    from Quartz import CGPreflightListenEventAccess

    try:
        from AVFoundation import AVCaptureDevice, AVMediaTypeAudio

        status = AVCaptureDevice.authorizationStatusForMediaType_(AVMediaTypeAudio)
        microphone = {0: "not_requested", 1: "restricted", 2: "denied", 3: "granted"}.get(
            status, "unavailable"
        )
    except ImportError:
        microphone = "unavailable"
    return {
        "microphone": microphone,
        "accessibility": bool(AXIsProcessTrusted()),
        "input_monitoring": bool(CGPreflightListenEventAccess()),
    }


def request_permission(kind):
    if kind == "microphone":
        from AVFoundation import AVCaptureDevice, AVMediaTypeAudio

        AVCaptureDevice.requestAccessForMediaType_completionHandler_(
            AVMediaTypeAudio, lambda allowed: None
        )
    elif kind == "accessibility":
        from ApplicationServices import AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt

        AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})
    elif kind == "input_monitoring":
        from Quartz import CGRequestListenEventAccess

        CGRequestListenEventAccess()
    else:
        raise ValueError("Unknown permission")
    return permissions()


def capture_target(context=False):
    from AppKit import NSWorkspace

    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    target = {
        "name": str(app.localizedName() or "Unknown"),
        "bundle": str(app.bundleIdentifier() or ""),
        "pid": int(app.processIdentifier()),
    }
    if context:
        from src.shared.text_injector import _save_clipboard

        target["context"] = _save_clipboard()
    return target


def insert_safely(text, target):
    from AppKit import NSPasteboard, NSPasteboardItem
    from ApplicationServices import AXIsProcessTrusted

    from src.shared.text_injector import _paste

    current = capture_target()
    if (
        not target.get("pid")
        or current["pid"] != target["pid"]
        or current["bundle"] != target["bundle"]
    ):
        return False, "Focus changed. Your text is ready in the workspace."
    if not AXIsProcessTrusted():
        return False, "Allow Accessibility for paste, or copy from the workspace."
    if current["bundle"] == "com.heyaaakash.roastmyaudio" or "python" in current["name"].lower():
        return False, "Your text is ready in the workspace."
    pasteboard = NSPasteboard.generalPasteboard()
    original = [
        [
            (str(kind), bytes(item.dataForType_(kind)))
            for kind in item.types()
            if item.dataForType_(kind) is not None
        ]
        for item in (pasteboard.pasteboardItems() or [])
    ]
    try:
        from AppKit import NSPasteboardTypeString

        pasteboard.clearContents()
        changed = pasteboard.changeCount()
        success = pasteboard.setString_forType_(text, NSPasteboardTypeString)
        changed = pasteboard.changeCount()
        if not success:
            return False, "Clipboard unavailable. Copy your text from the workspace."
        _paste()
        return True, "Paste sent. Review the destination."
    except Exception:
        return False, "Paste unavailable. Your text is ready in the workspace."
    finally:
        # Preserve all clipboard formats; don't overwrite a newer user clipboard change.
        if "changed" in locals() and pasteboard.changeCount() == changed:
            items = []
            for saved in original:
                item = NSPasteboardItem.alloc().init()
                for kind, data in saved:
                    item.setData_forType_(data, kind)
                items.append(item)
            pasteboard.clearContents()
            if items:
                pasteboard.writeObjects_(items)


def login_status():
    if not getattr(sys, "frozen", False):
        return {
            "available": False,
            "enabled": False,
            "message": "Available in the installed Mac app",
        }
    try:
        from ServiceManagement import SMAppService

        status = int(SMAppService.mainAppService().status())
        return {"available": True, "enabled": status == 1, "requires_approval": status == 2}
    except Exception:
        return {
            "available": False,
            "enabled": False,
            "message": "Login items are unavailable on this Mac",
        }


def set_login(enabled):
    if type(enabled) is not bool or not login_status()["available"]:
        raise ValueError("Install the Mac app to manage launch at login")
    from ServiceManagement import SMAppService

    service = SMAppService.mainAppService()
    success, error = (
        service.registerAndReturnError_(None)
        if enabled
        else service.unregisterAndReturnError_(None)
    )
    if not success:
        raise ValueError(
            "Could not change launch at login. Review System Settings → General → Login Items."
        )
    return login_status()


def diagnostics():
    import importlib.metadata

    from config import PROJECT_ROOT
    from src.shared.settings import load

    preferences = load()
    return {
        "version": (PROJECT_ROOT / "VERSION").read_text().strip(),
        "os": platform.mac_ver()[0],
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "bundled": bool(getattr(sys, "frozen", False)),
        "permissions": permissions(),
        "speech_model": preferences["model"],
        "language": preferences["language"],
        "cleanup_enabled": preferences["llm_enabled"],
        "dependencies": {
            name: importlib.metadata.version(name)
            for name in ("faster-whisper", "Flask", "sounddevice")
        },
    }


def export_diagnostics():
    from AppKit import NSModalResponseOK, NSSavePanel

    panel = NSSavePanel.savePanel()
    panel.setNameFieldStringValue_("roastmyaudio-diagnostics.json")
    if panel.runModal() != NSModalResponseOK:
        return {"saved": False}
    Path(str(panel.URL().path())).write_text(json.dumps(diagnostics(), indent=2), encoding="utf-8")
    return {"saved": True}


def install_reopen_handler(callback):
    """Finder reopening an already-running accessory app reveals its workspace."""
    import objc
    from Foundation import NSAppleEventManager, NSObject

    class RMAReopenEventHandler(NSObject):
        @objc.signature(b"v@:@@")
        def handleReopen_reply_(self, event, reply):
            self.callback()

    handler = RMAReopenEventHandler.alloc().init()
    handler.callback = callback
    NSAppleEventManager.sharedAppleEventManager().setEventHandler_andSelector_forEventClass_andEventID_(
        handler, "handleReopen:reply:", 0x61657674, 0x72617070
    )
    return handler


def remove_reopen_handler():
    from Foundation import NSAppleEventManager

    NSAppleEventManager.sharedAppleEventManager().removeEventHandlerForEventClass_andEventID_(
        0x61657674, 0x72617070
    )
