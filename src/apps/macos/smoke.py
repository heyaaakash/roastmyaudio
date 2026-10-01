"""Actual Cocoa/WebKit and packaged-entry smoke with fictional adapters and temp data."""

import time
from unittest.mock import patch

import numpy as np


def run():
    from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
    from Foundation import NSDate, NSRunLoop

    from config import DATA_DIR
    from src.apps.macos import menubar_dictation as native
    from src.apps.macos.session_controller import SessionController
    from src.apps.macos.workspace_server import WorkspaceServer
    from src.apps.macos.workspace_window import WorkspaceWindow, _native_types
    from src.apps.web.app import app
    from src.shared import history, settings, workspace_state

    NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    NSApplication.sharedApplication().finishLaunching()

    def pump(check, timeout=15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.03))
            if check():
                return
        raise AssertionError("Native smoke timed out")

    def evaluate(webview, javascript):
        replies = []
        webview.evaluateJavaScript_completionHandler_(
            javascript, lambda result, error: replies.append((result, error))
        )
        pump(lambda: bool(replies))
        value, error = replies[0]
        assert error is None, str(error)
        return value

    class FictionalRecorder:
        def __init__(self, **_):
            self.closed = False

        def start(self, extra_callback=None):
            self.callback = extra_callback

        def stop(self):
            self.closed = True
            return np.ones(16000, dtype=np.float32) * 0.1

    created = []

    def factory(**_):
        recorder = FictionalRecorder()
        created.append(recorder)
        return recorder

    def controller_factory(**kwargs):
        kwargs["recorder_factory"] = factory
        kwargs["processor"] = lambda *_: {
            "raw": "A fictional practice thought.",
            "cleaned": "A fictional practice thought.",
            "formatted": "A fictional practice thought.",
            "latency_ms": 0,
        }
        return SessionController(**kwargs)

    actual_permissions = native.platform_services.permissions()
    assert actual_permissions["microphone"] != "unavailable"
    assert native.platform_services.diagnostics()["version"]
    permission = {"microphone": "granted", "accessibility": False, "input_monitoring": False}
    with (
        patch("AppKit.NSPasteboard") as clipboard,
        patch("AppKit.NSSavePanel") as panel_type,
        patch.object(native.platform_services, "permissions", return_value=permission),
        patch.object(
            native.platform_services,
            "login_status",
            return_value={"available": False, "enabled": False},
        ),
        patch.object(
            native,
            "WorkspaceWindow",
            side_effect=lambda url, **kwargs: WorkspaceWindow(url, persistent=False, **kwargs),
        ),
    ):
        _native_types.cache_clear()
        clipboard.generalPasteboard.return_value.setString_forType_.return_value = True
        panel = panel_type.savePanel.return_value
        panel.runModal.return_value = 1
        panel.URL.return_value.path.return_value = str(DATA_DIR / "fictional-export.txt")
        settings.set("llm_enabled", False)
        existing = WorkspaceServer(app, preferred_port=0)
        existing.start()
        desktop = None
        try:
            with patch.object(native, "FLASK_PORT", existing._server.server_port):
                desktop = native.WhisperMenuBarApp(
                    controller_factory=controller_factory, enable_hooks=False
                )
            assert desktop._workspace_server.base_url != existing.base_url
            desktop._reopen_handler.handleReopen_reply_(None, None)
            window = desktop._workspace_window
            pump(lambda: not window.webview.isLoading() and bool(window.webview.URL()))
            webview = window.webview
            pump(lambda: evaluate(webview, "document.querySelector('#emptyAction') !== null"))
            pump(lambda: evaluate(webview, "document.querySelector('#setupDialog').open"))
            evaluate(webview, "document.querySelector('#practiceBtn').click(); true")
            pump(lambda: desktop._controller.snapshot()["phase"] == "recording")
            assert len(created) == 1
            # Finishing via the menu controls the same workspace-started session.
            desktop._on_dictate(None)
            pump(lambda: desktop._controller.snapshot()["text"] != "")
            pump(
                lambda: evaluate(
                    webview, "document.querySelector('#finishSetupBtn').disabled === false"
                )
            )
            assert created[0].closed and len(history.load()) == 1
            evaluate(webview, "document.querySelector('#finishSetupBtn').click(); true")
            pump(lambda: workspace_state.load()["onboarding_complete"])
            desktop._on_open_scratchpad(None)
            pump(lambda: evaluate(webview, "location.hash") == "#scratchpad")
            evaluate(
                webview,
                "document.querySelector('#scratchpad').value = 'A durable fictional native draft.'; document.querySelector('#scratchpad').dispatchEvent(new Event('input')); true",
            )
            pump(lambda: workspace_state.load()["draft"] == "A durable fictional native draft.")
            window.window.performClose_(None)
            desktop._on_open_scratchpad(None)
            assert window.webview is webview
            assert (
                evaluate(webview, "document.querySelector('#scratchpad').value")
                == workspace_state.load()["draft"]
            )
            evaluate(
                webview,
                "window.bridgeProbe = 'waiting'; window.roastmyaudioDesktop.copy('Fictional copy').then(() => window.bridgeProbe = 'copied'); true",
            )
            pump(lambda: evaluate(webview, "window.bridgeProbe") == "copied")
            assert (
                clipboard.generalPasteboard.return_value.setString_forType_.call_args.args[0]
                == "Fictional copy"
            )
            evaluate(
                webview,
                "window.bridgeProbe = 'waiting'; window.roastmyaudioDesktop.exportText('Fictional export').then(() => window.bridgeProbe = 'exported'); true",
            )
            pump(lambda: evaluate(webview, "window.bridgeProbe") == "exported")
            assert (DATA_DIR / "fictional-export.txt").read_text() == "Fictional export"
            desktop._on_open_preferences(None)
            pump(lambda: evaluate(webview, "location.hash") == "#settings")
            assert (
                app.test_client()
                .post("/api/settings", json={"model": "small", "language": "auto"})
                .status_code
                == 200
            )
            desktop._sync_preferences(None)
            assert desktop._selected_model == "small"
            # Reloading the renderer also recovers the draft from durable app storage.
            webview.reload()
            pump(lambda: not webview.isLoading())
            pump(
                lambda: (
                    evaluate(webview, "document.querySelector('#scratchpad').value")
                    == "A durable fictional native draft."
                )
            )
            desktop._controller.start()
            desktop._on_sleep()
            assert desktop._controller.snapshot()["phase"] == "idle" and created[-1].closed
            desktop._on_wake()
            desktop._shutdown()
            assert not desktop._workspace_server.running and existing.running
            desktop._shutdown()
            print(
                "Unified native smoke passed: real Cocoa/WebKit, setup/practice via one controller, menu stop, durable draft bridge/reload/reopen, clipboard/export round trips (OS endpoints mocked), shared settings, reopen/sleep callbacks, port fallback and owned shutdown. Synthetic capture/inference; no permission prompts, global hooks, private clipboard, model downloads or real paste."
            )
        finally:
            if desktop:
                desktop._shutdown()
            existing.stop()


def run_model_smoke(audio_path):
    from faster_whisper.audio import decode_audio

    from src.apps.macos.session_controller import SessionController
    from src.shared import history, settings

    settings.set("llm_enabled", False)
    audio = decode_audio(str(audio_path), sampling_rate=16000)

    class Recorder:
        def __init__(self, **_):
            pass

        def start(self, **_):
            pass

        def stop(self):
            return audio

    session = SessionController(Recorder, lambda: {}, lambda *_: None)
    try:
        session.start(practice=True)
        session.stop()
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline and session.snapshot()["phase"] == "processing":
            time.sleep(0.1)
        state = session.snapshot()
        assert state["text"], state["error"]
        records = history.load()
        assert len(records) == 1 and records[0]["status"] == "completed"
        print(
            f"Actual native-controller model smoke passed: {len(state['text'].split())} recognized words; saved one recording. Synthetic speech only."
        )
    finally:
        session.shutdown()
