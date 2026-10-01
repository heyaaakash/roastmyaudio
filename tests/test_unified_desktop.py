"""Behavioral checks for the single session and durable workspace, without native capture."""

import threading
import time

import numpy as np
import pytest

from src.apps.macos.app_lifecycle import AppInstance, import_source_data
from src.apps.macos.session_controller import SessionController
from src.apps.web.app import app
from src.shared import history, personalization, settings, workspace_state


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    (tmp_path / "recordings").mkdir()
    monkeypatch.setattr(history, "HISTORY_PATH", tmp_path / "history.json")
    monkeypatch.setattr(history, "RECORDINGS_DIR", tmp_path / "recordings")
    monkeypatch.setattr(settings, "SETTINGS_PATH", tmp_path / "settings.json")
    monkeypatch.setattr(workspace_state, "WORKSPACE_PATH", tmp_path / "workspace.json")
    monkeypatch.setattr(personalization, "PERSONALIZATION_PATH", tmp_path / "personalization.json")
    return tmp_path


class Recorder:
    def __init__(self, device_id=None):
        self.device_id = device_id
        self.started = self.stopped = 0

    def start(self, extra_callback=None):
        self.started += 1

    def stop(self):
        self.stopped += 1
        return np.ones(16000, dtype=np.float32) * 0.1


def wait_for(check):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.01)
    raise AssertionError("Session failed to reach expected state")


def make_session(processor=None):
    recorder = Recorder()
    insertions = []
    target = {"name": "Fictional Editor", "bundle": "org.fixture.editor", "pid": 12}
    controller = SessionController(
        lambda **_: recorder,
        lambda: target,
        lambda text, captured: insertions.append((text, captured)),
        processor=processor
        or (
            lambda *_: {
                "raw": "A thought.",
                "cleaned": "A thought.",
                "formatted": "A thought.",
                "latency_ms": 0,
            }
        ),
    )
    return controller, recorder, insertions


def test_buttons_and_shortcut_share_one_capture_and_history(isolated):
    gate = threading.Event()

    def process(*_):
        gate.wait(2)
        return {
            "raw": "Fictional words.",
            "cleaned": "Fictional words.",
            "formatted": "Fictional words.",
            "latency_ms": 0,
        }

    session, recorder, insertions = make_session(process)
    try:
        session.start(source="hotkey")
        with pytest.raises(ValueError):
            session.start(source="workspace")
        session.stop()
        session.stop()
        with pytest.raises(ValueError):
            session.start(source="menu")
        assert recorder.started == recorder.stopped == 1
        assert len(history.load()) == 1 and history.load()[0]["status"] == "processing"
        gate.set()
        wait_for(lambda: session.snapshot()["phase"] == "idle")
        assert len(history.load()) == 1
        assert insertions[0][1]["pid"] == 12
    finally:
        gate.set()
        session.shutdown()


def test_failure_retry_updates_same_saved_record_without_pasting(isolated):
    count = 0

    def process(*_):
        nonlocal count
        count += 1
        if count == 1:
            raise RuntimeError("fixture inference failure")
        return {
            "raw": "Recovered words.",
            "cleaned": "Recovered words.",
            "formatted": "Recovered words.",
            "latency_ms": 0,
        }

    session, recorder, insertions = make_session(process)
    try:
        session.start(source="hotkey")
        session.stop()
        wait_for(lambda: session.snapshot()["can_retry"])
        first = history.load()[0]
        assert (
            first["status"] == "failed" and (isolated / "recordings" / first["audio_file"]).exists()
        )
        session.retry()
        wait_for(lambda: session.snapshot()["text"] == "Recovered words.")
        records = history.load()
        assert (
            len(records) == 1
            and records[0]["id"] == first["id"]
            and records[0]["status"] == "completed"
        )
        assert recorder.stopped == 1 and not insertions
    finally:
        session.shutdown()


def test_cancel_and_quit_suppress_late_results_and_release_capture(isolated):
    entered, finish = threading.Event(), threading.Event()

    def process(*_):
        entered.set()
        finish.wait(2)
        return {
            "raw": "Late words",
            "cleaned": "Late words",
            "formatted": "Late words",
            "latency_ms": 0,
        }

    session, recorder, insertions = make_session(process)
    session.start(source="hotkey")
    session.stop()
    assert entered.wait(1)
    session.cancel()
    session.shutdown()
    finish.set()
    time.sleep(0.05)
    assert not insertions and not session.snapshot()["text"]
    assert history.load()[0]["status"] == "failed"
    assert recorder.stopped == 1
    second, recorder2, _ = make_session()
    second.start()
    second.shutdown()
    second.shutdown()
    assert recorder2.stopped == 1


def test_recording_snapshots_preferences_and_workspace_does_not_paste(isolated):
    observed = []

    def process(audio, preferences, target, strict):
        observed.append((preferences["language"], strict, target["name"]))
        return {"raw": "Words", "cleaned": "Words", "formatted": "Words", "latency_ms": 0}

    session, _, insertions = make_session(process)
    try:
        settings.set("language", "hi")
        session.start(strict=True, practice=True)
        settings.set("language", "en")
        session.stop()
        wait_for(lambda: bool(session.snapshot()["text"]))
        assert observed == [("hi", True, "Practice")]
        assert not insertions and session.snapshot()["practice"]
    finally:
        session.shutdown()


def test_microphone_failure_closes_stream_and_does_not_create_history(isolated):
    class Denied(Recorder):
        def start(self, **_):
            raise RuntimeError("Denied")

    recorder = Denied()
    session = SessionController(lambda **_: recorder, lambda: {}, lambda *_: None)
    try:
        assert session.start()["phase"] == "error"
        assert recorder.stopped == 1 and not history.load()
    finally:
        session.shutdown()


def test_draft_theme_survive_different_ports_and_recreated_client(isolated):
    client = app.test_client()
    first = "http://127.0.0.1:51111"
    second = "http://127.0.0.1:52222"
    assert (
        client.post(
            "/api/workspace",
            base_url=first,
            json={"draft": "A durable fictional draft", "theme": "dark"},
        ).status_code
        == 200
    )
    recovered = app.test_client().get("/api/workspace", base_url=second).get_json()
    assert recovered["draft"] == "A durable fictional draft" and recovered["theme"] == "dark"
    client.post("/api/workspace", json={"draft": "Old browser copy", "only_if_empty": True})
    assert workspace_state.load()["draft"] == recovered["draft"]
    for payload in [
        {"theme": []},
        {"draft": None},
        {"onboarding_complete": "yes"},
        {"arbitrary": "bad"},
    ]:
        assert client.post("/api/workspace", json=payload).status_code == 400
    assert workspace_state.load()["draft"] == recovered["draft"]


def test_personalization_is_explicit_bounded_and_uses_whole_snippet(isolated):
    library = {
        "corrections": [{"heard": "graph queue ell", "write": "GraphQL"}],
        "snippets": [{"trigger": "my sign off", "text": "Thank you,\nA fictional name"}],
        "app_styles": [{"app": "Fictional Editor", "style": "verbatim"}],
    }
    personalization.save(library)
    assert personalization.apply("Use graph queue ell today.")[0] == "Use GraphQL today."
    assert personalization.apply("My sign off.") == ("Thank you,\nA fictional name", True)
    assert not personalization.apply("Please use my sign off tomorrow")[1]
    assert personalization.style_for("fictional editor") == "verbatim"
    assert personalization.style_for("Another app") == "default"
    with pytest.raises(ValueError):
        personalization.save({**library, "corrections": library["corrections"] * 2})
    assert app.test_client().post("/api/personalization", json={"unknown": []}).status_code == 400


def test_single_instance_and_non_destructive_import(tmp_path):
    source, destination = tmp_path / "source", tmp_path / "destination"
    source.mkdir()
    (source / "settings.json").write_text('{"language":"hi"}')
    (source / "recordings").mkdir()
    (source / "recordings/fixture.wav").write_bytes(b"fixture")
    (source / "private-unrelated.txt").write_text("do not migrate")
    assert import_source_data(source, destination)
    assert (source / "settings.json").exists() and (destination / "recordings/fixture.wav").exists()
    assert not (destination / "private-unrelated.txt").exists()
    assert not import_source_data(source, destination)
    first, second = AppInstance(destination), AppInstance(destination)
    assert first.acquire() and not second.acquire()
    first.release()
    assert second.acquire()
    second.release()


def test_malformed_import_does_not_create_partial_data(tmp_path):
    source, destination = tmp_path / "source", tmp_path / "destination"
    source.mkdir()
    (source / "history.json").write_text('[]')
    (source / "settings.json").write_text('{broken')
    assert not import_source_data(source, destination)
    assert not (destination / "history.json").exists()
    assert not (destination / "source-import.json").exists()


def test_restart_recovers_interrupted_audio_and_reopen_request(isolated):
    from src.apps.macos.app_lifecycle import consume_reopen, request_reopen

    record = history.save_recording(audio=np.ones(16000), status="processing")
    history.recover_interrupted()
    assert history.get_recording(record["id"])["status"] == "failed"
    assert (isolated / "recordings" / record["audio_file"]).exists()
    request_reopen(isolated)
    assert consume_reopen(isolated) and not consume_reopen(isolated)


def test_cancel_releases_disconnected_input_even_if_close_raises(isolated):
    class Disconnected(Recorder):
        def stop(self):
            self.stopped += 1
            raise OSError("disconnected fixture")

    recorder = Disconnected()
    session = SessionController(lambda **_: recorder, lambda: {}, lambda *_: None)
    session.start()
    assert session.cancel()["phase"] == "idle"
    session.shutdown()
    assert recorder.stopped == 1


@pytest.mark.parametrize("scenario", ["focus_changed", "restore", "new_clipboard", "write_failed"])
def test_native_paste_checks_target_and_preserves_clipboard(monkeypatch, scenario):
    import sys
    from types import SimpleNamespace

    from src.apps.macos import platform_services

    class Item:
        def __init__(self):
            self.data = {"public.png": b"fictional image", "public.utf8-plain-text": b"old"}

        @classmethod
        def alloc(cls):
            return cls()

        def init(self):
            self.data = {}
            return self

        def types(self):
            return list(self.data)

        def dataForType_(self, kind):
            return self.data[kind]

        def setData_forType_(self, value, kind):
            self.data[kind] = value

    class Clipboard:
        def __init__(self):
            self.items = [Item()]
            self.revision = 1

        def pasteboardItems(self):
            return self.items

        def changeCount(self):
            return self.revision

        def clearContents(self):
            self.items = []
            self.revision += 1

        def setString_forType_(self, value, kind):
            self.revision += 1
            return scenario != "write_failed"

        def writeObjects_(self, items):
            self.items = items
            self.revision += 1

    clipboard = Clipboard()
    pasted = []
    target = {"pid": 7, "bundle": "org.fixture.editor", "name": "Fictional Editor"}
    monkeypatch.setattr(platform_services, "capture_target", lambda: {**target, "pid": 8} if scenario == "focus_changed" else target)
    monkeypatch.setitem(sys.modules, "AppKit", SimpleNamespace(
        NSPasteboard=SimpleNamespace(generalPasteboard=lambda: clipboard),
        NSPasteboardItem=Item, NSPasteboardTypeString="public.utf8-plain-text"))
    monkeypatch.setitem(sys.modules, "ApplicationServices", SimpleNamespace(AXIsProcessTrusted=lambda: True))

    def paste():
        pasted.append(True)
        if scenario == "new_clipboard":
            clipboard.revision += 1

    monkeypatch.setitem(sys.modules, "src.shared.text_injector", SimpleNamespace(_paste=paste))
    success, _ = platform_services.insert_safely("Fictional words", target)
    assert success == (scenario in {"restore", "new_clipboard"})
    assert bool(pasted) == success
    if scenario == "focus_changed":
        assert clipboard.revision == 1
    elif scenario in {"restore", "write_failed"}:
        assert clipboard.items[0].data == {"public.png": b"fictional image", "public.utf8-plain-text": b"old"}
    else:
        assert clipboard.revision == 4  # A newer user copy is never overwritten.
