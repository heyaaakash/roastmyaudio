"""RoastMyAudio's menu bar shell; capture, data and workspace share one session."""

import os
import signal
import sys
import threading
import webbrowser

import rumps
from AppKit import (
    NSEvent,
    NSEventMaskFlagsChanged,
    NSEventModifierFlagFunction,
    NSRunningApplication,
)
from pynput import keyboard
from PyObjCTools import AppHelper

from config import DATA_DIR, FLASK_PORT, PROJECT_ROOT, UPDATES_URL
from src.apps.macos import platform_services
from src.apps.macos.app_lifecycle import (
    AppInstance,
    consume_reopen,
    import_source_data,
    request_reopen,
)
from src.apps.macos.audio_recorder import AudioRecorder, list_input_devices
from src.apps.macos.hud_overlay import DictationOverlay
from src.apps.macos.session_controller import SessionController
from src.apps.macos.workspace_server import WorkspaceServer
from src.apps.macos.workspace_window import WorkspaceWindow
from src.shared import history, settings, workspace_state
from src.shared.llm_cleanup import cleanup_llm


class WhisperMenuBarApp(rumps.App):
    def __init__(self, controller_factory=SessionController, enable_hooks=True):
        super().__init__("RoastMyAudio", title="◉", quit_button=None)
        self._shutdown_complete = False
        self._lock = threading.RLock()
        self._workspace_window = None
        self._hotkey_listener = None
        self._fn_monitors = []
        self._pressed = set()
        self._shortcut_down = False
        self._fn_down = self._fallback_down = False
        self._enable_hooks = enable_hooks
        self._overlay = DictationOverlay()
        self._last_text = ""
        self._rendered_phase = "idle"
        self._selected_model = settings.load()["model"]
        self._settings = settings.load()
        self._controller = controller_factory(
            recorder_factory=AudioRecorder,
            capture_target=self._capture_target,
            insert_text=self._insert,
            notify=self._session_changed,
        )
        self._dictate_item = rumps.MenuItem("Start dictating", callback=self._on_dictate)
        self._pause_item = rumps.MenuItem("Pause shortcuts", callback=self._on_pause)
        self._dashboard_item = rumps.MenuItem(
            "Open Workspace…", callback=lambda _: self._open_workspace()
        )
        self._history_item = rumps.MenuItem(
            "Recent Thoughts…", callback=lambda _: self._open_workspace()
        )
        self._preferences_item = rumps.MenuItem(
            "Preferences…", callback=lambda _: self._open_workspace("settings")
        )
        self._copy_item = rumps.MenuItem("Copy last thought", callback=self._on_copy)
        self._status_item = rumps.MenuItem("Ready when you are")
        self._status_item.set_callback(None)
        self.menu = [
            self._dictate_item,
            self._pause_item,
            self._dashboard_item,
            self._history_item,
            self._preferences_item,
            None,
            self._copy_item,
            self._status_item,
            None,
            rumps.MenuItem("Quit RoastMyAudio", callback=self._on_quit),
        ]
        from src.apps.web.app import app as web_app

        self._workspace_server = WorkspaceServer(web_app, preferred_port=FLASK_PORT)
        self._workspace_server.start()
        self._reopen_handler = platform_services.install_reopen_handler(self._open_workspace)
        self._preferences_timer = rumps.Timer(self._sync_preferences, 1)
        rumps.events.on_sleep.register(self._on_sleep)
        rumps.events.on_wake.register(self._on_wake)
        rumps.events.before_quit.register(self._shutdown)
        self._preferences_timer.start()
        self._sync_preferences(None)

    def _capture_target(self):
        return platform_services.capture_target(context=settings.load()["context_awareness"])

    def _insert(self, text, target):
        AppHelper.callAfter(self._insert_on_main, text, target)

    def _insert_on_main(self, text, target):
        if self._shutdown_complete or self._controller.snapshot()["text"] != text:
            return
        success, message = platform_services.insert_safely(text, target)
        self._status_item.title = message
        if self._workspace_window:
            self._workspace_window.dispatch(
                "rma-insertion", {"success": success, "message": message}
            )
        if not success:
            self._open_workspace()

    def _session_changed(self, state):
        AppHelper.callAfter(self._render_session, state)

    def _render_session(self, state):
        if self._shutdown_complete:
            return
        phase = state["phase"]
        self.title = (
            "●" if phase == "recording" else "◌" if phase in {"processing", "preparing"} else "◉"
        )
        self._dictate_item.title = "Finish dictating" if phase == "recording" else "Start dictating"
        self._status_item.title = state["message"]
        if phase == "recording":
            if self._rendered_phase != phase:
                self._overlay.show(feedback=self._settings["haptics_enabled"])
            self._overlay.set_title("Listening")
            self._overlay.set_mode_badge(
                "Workspace" if state["source"] == "workspace" else "Dictation"
            )
            self._overlay.set_audio_level(state["level"])
        elif phase == "processing":
            self._overlay.set_title("Turning voice into words…")
            self._overlay.reset_waveform()
        elif self._rendered_phase in {"recording", "processing"}:
            self._overlay.hide(feedback=self._settings["haptics_enabled"])
        self._rendered_phase = phase
        if state["text"]:
            self._last_text = state["text"]
        if self._workspace_window:
            self._workspace_window.dispatch("rma-session", self._desktop_state())

    def _desktop_state(self):
        return {
            **self._controller.snapshot(),
            "permissions": platform_services.permissions(),
            "login": platform_services.login_status(),
            "settings": settings.load(),
            "workspace": workspace_state.load(),
        }

    def _handle_command(self, action, payload):
        if action == "state":
            return self._desktop_state()
        if action == "start":
            if platform_services.permissions()["microphone"] != "granted":
                raise ValueError("Allow Microphone in setup before dictating")
            self._controller.start(
                source="workspace",
                strict=payload.get("strict", False) is True,
                practice=payload.get("practice", False) is True,
            )
        elif action == "stop":
            self._controller.stop()
        elif action == "cancel":
            self._controller.cancel()
        elif action == "retry":
            self._controller.retry()
        elif action == "prepare":
            self._controller.prepare()
        elif action == "permission":
            return platform_services.request_permission(payload.get("kind"))
        elif action == "devices":
            return [{"id": index, "name": name} for index, name in list_input_devices()]
        elif action == "login":
            return platform_services.set_login(payload.get("enabled"))
        elif action == "diagnostics":
            return platform_services.export_diagnostics()
        elif action == "updates":
            webbrowser.open(UPDATES_URL)
            return {"opened": True}
        elif action == "onboarding":
            workspace_state.update({"onboarding_complete": True})
            return workspace_state.load()
        else:
            raise ValueError("Unsupported desktop command")
        return self._desktop_state()

    def _open_workspace(self, view="dictation", browser=False):
        base_url = self._workspace_server.start()
        if browser:
            from src.apps.macos.workspace_server import workspace_url

            webbrowser.open(workspace_url(base_url, view))
            return
        if self._workspace_window is None:
            self._workspace_window = WorkspaceWindow(base_url, command_handler=self._handle_command)
        self._workspace_window.show(view)

    def _sync_preferences(self, _):
        if self._shutdown_complete:
            return
        if consume_reopen(DATA_DIR):
            self._open_workspace()
        self._settings = settings.load()
        self._selected_model = self._settings["model"]
        self._pause_item.title = (
            "Pause shortcuts" if self._settings["shortcuts_enabled"] else "Resume shortcuts"
        )
        if self._enable_hooks and self._hotkey_listener is None:
            permission = platform_services.permissions()
            if permission["input_monitoring"]:
                try:
                    self._hotkey_listener = keyboard.Listener(
                        on_press=self._on_key_press, on_release=self._on_key_release
                    )
                    self._hotkey_listener.start()
                    self._fn_monitors = [
                        NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                            NSEventMaskFlagsChanged, self._on_flags_changed
                        ),
                        NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
                            NSEventMaskFlagsChanged, self._on_flags_changed
                        ),
                    ]
                except Exception:
                    self._hotkey_listener = None
        if self._workspace_window and self._workspace_window.webview:
            self._workspace_window.dispatch("rma-session", self._desktop_state())

    def _shortcut(self, down, source="fallback"):
        AppHelper.callAfter(self._shortcut_on_main, down, source)

    def _shortcut_on_main(self, down, source):
        if not self._settings["shortcuts_enabled"]:
            return
        with self._lock:
            if source == "fn":
                self._fn_down = down
            else:
                self._fallback_down = down
            down = self._fn_down or self._fallback_down
            changed = down != self._shortcut_down
            self._shortcut_down = down
            if not changed:
                return
            if self._settings["dictation_mode"] == "hands_free":
                if down:
                    self._toggle_capture("hotkey")
            elif down:
                self._start_capture("hotkey")
            elif (
                self._controller.snapshot()["phase"] == "recording"
                and self._controller.snapshot()["source"] == "hotkey"
            ):
                self._controller.stop()

    def _on_flags_changed(self, event):
        if self._settings["hotkey"] == "fn":
            self._shortcut(bool(int(event.modifierFlags()) & NSEventModifierFlagFunction), "fn")
        return event

    def _on_key_press(self, key):
        if key == keyboard.Key.esc and self._controller.snapshot()["phase"] in {
            "recording",
            "processing",
        }:
            AppHelper.callAfter(self._controller.cancel)
        self._pressed.add(key)
        self._update_fallback()

    def _on_key_release(self, key):
        self._pressed.discard(key)
        self._update_fallback()

    def _update_fallback(self):
        ctrl = any(
            key in self._pressed
            for key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r)
        )
        alt = any(
            key in self._pressed
            for key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r)
        )
        d = any(
            getattr(key, "char", "").lower() == "d"
            for key in self._pressed
            if getattr(key, "char", None)
        )
        self._shortcut(ctrl and alt and d)

    def _start_capture(self, source):
        try:
            if platform_services.permissions()["microphone"] != "granted":
                AppHelper.callAfter(self._open_workspace, "settings")
                return
            self._controller.start(source=source)
        except ValueError as error:
            AppHelper.callAfter(setattr, self._status_item, "title", str(error))

    def _toggle_capture(self, source):
        if self._controller.snapshot()["phase"] == "recording":
            self._controller.stop()
        else:
            self._start_capture(source)

    def _on_dictate(self, _):
        # The menu itself is the foreground context; workspace capture avoids guessing a destination.
        self._open_workspace()
        self._toggle_capture("workspace")

    def _on_pause(self, _):
        settings.set("shortcuts_enabled", not self._settings["shortcuts_enabled"])
        self._fn_down = self._fallback_down = self._shortcut_down = False
        if (
            self._controller.snapshot()["phase"] == "recording"
            and self._controller.snapshot()["source"] == "hotkey"
        ):
            self._controller.cancel()
        self._sync_preferences(None)

    def _on_copy(self, _):
        if self._last_text:
            from src.shared.text_injector import _write_clipboard

            _write_clipboard(self._last_text)

    def _on_open_dashboard(self, _):
        self._open_workspace()

    def _on_open_scratchpad(self, _):
        self._open_workspace("scratchpad")

    def _on_open_preferences(self, _):
        self._open_workspace("settings")

    def _on_show_dictionary(self, _):
        self._open_workspace("dictionary")

    def _shutdown(self):
        if self._shutdown_complete:
            return
        self._shutdown_complete = True
        rumps.events.on_sleep.unregister(self._on_sleep)
        rumps.events.on_wake.unregister(self._on_wake)
        rumps.events.before_quit.unregister(self._shutdown)
        self._preferences_timer.stop()
        platform_services.remove_reopen_handler()
        self._reopen_handler = None
        self._controller.shutdown()
        if self._hotkey_listener:
            self._hotkey_listener.stop()
        for monitor in self._fn_monitors:
            if monitor:
                NSEvent.removeMonitor_(monitor)
        self._overlay.hide(feedback=False)
        if self._workspace_window:
            self._workspace_window.close()
        self._workspace_server.stop()
        cleanup_llm()

    def _on_sleep(self):
        if self._controller.snapshot()["phase"] in {"recording", "processing", "preparing"}:
            self._controller.cancel()
        self._fn_down = self._fallback_down = self._shortcut_down = False
        self._pressed.clear()

    def _on_wake(self):
        self._sync_preferences(None)

    def _on_quit(self, _):
        self._shutdown()
        rumps.quit_application()


def main():
    if "--model-smoke" in sys.argv:
        from src.apps.macos.smoke import run_model_smoke

        run_model_smoke(sys.argv[sys.argv.index("--model-smoke") + 1])
        return
    if "--smoke" in sys.argv:
        from src.apps.macos.smoke import run

        run()
        return
    instance = AppInstance(DATA_DIR)
    if not instance.acquire():
        request_reopen(DATA_DIR)
        try:
            owner = int((DATA_DIR / "desktop-owner.pid").read_text())
            app = NSRunningApplication.runningApplicationWithProcessIdentifier_(owner)
            if app:
                app.activateWithOptions_(3)
        except (OSError, ValueError):
            pass
        return
    (DATA_DIR / "desktop-owner.pid").write_text(str(os.getpid()))
    desktop = None
    try:
        if not getattr(sys, "frozen", False):
            import_source_data(PROJECT_ROOT / "data", DATA_DIR)
        history.recover_interrupted()
        desktop = WhisperMenuBarApp()

        def terminate(*_):
            desktop._on_quit(None)

        signal.signal(signal.SIGINT, terminate)
        signal.signal(signal.SIGTERM, terminate)
        if not workspace_state.load()["onboarding_complete"]:
            AppHelper.callAfter(desktop._open_workspace)
        desktop.run()
    finally:
        if desktop:
            desktop._shutdown()
        instance.release()


if __name__ == "__main__":
    main()
