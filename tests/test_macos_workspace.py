"""Lifecycle and native boundary checks without Cocoa, sockets, or microphone access."""

import threading
from unittest.mock import Mock

import pytest

from src.apps.macos.workspace_server import WorkspaceServer, same_origin, workspace_url
from src.apps.macos.workspace_window import validate_bridge_message
from src.shared import settings


class FakeServer:
    def __init__(self, port):
        self.server_port = port or 51321
        self.stopped = threading.Event()
        self.started = threading.Event()
        self.closed = False

    def serve_forever(self):
        self.started.set()
        self.stopped.wait(5)

    def shutdown(self):
        self.stopped.set()

    def server_close(self):
        self.closed = True


def test_owned_server_falls_back_and_does_not_recreate_on_open():
    server = FakeServer(0)
    factory = Mock(side_effect=[OSError("busy"), server])
    workspace = WorkspaceServer(object(), preferred_port=5000, server_factory=factory)
    assert workspace.start() == "http://127.0.0.1:51321"
    assert server.started.wait(1)
    assert workspace.start() == workspace.base_url
    assert [call.args[1] for call in factory.call_args_list] == [5000, 0]
    workspace.stop()
    workspace.stop()
    assert server.closed and server.stopped.is_set() and not workspace.running
    with pytest.raises(RuntimeError):
        _ = workspace.base_url


def test_restart_replaces_only_owned_server():
    first, second = FakeServer(51000), FakeServer(51001)
    workspace = WorkspaceServer(object(), server_factory=Mock(side_effect=[first, second]))
    workspace.start()
    assert workspace.restart().endswith(":51001")
    assert first.closed and not second.closed
    workspace.stop()
    assert second.closed


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:5000/",
        "http://localhost:5000/",
        "http://127.0.0.1:5001/",
        "file:///tmp/index.html",
        "http://127.0.0.1:wrong/",
        "https://example.com",
    ],
)
def test_native_boundary_rejects_other_origins(url):
    assert not same_origin(url, "http://127.0.0.1:5000")
    with pytest.raises(ValueError):
        validate_bridge_message(
            {"id": 1, "action": "copy", "text": "Fictional"}, url, "http://127.0.0.1:5000", True
        )


def test_bridge_accepts_main_frame_bounded_text_only():
    base = "http://127.0.0.1:5000"
    body = {"id": 2, "action": "export", "text": "A fictional thought."}
    assert validate_bridge_message(body, base + "/#scratchpad", base, True) == body
    for invalid in [
        dict(body, id=True),
        dict(body, action="shell"),
        dict(body, text="x" * 2_000_001),
        dict(body, text=3),
    ]:
        with pytest.raises(ValueError):
            validate_bridge_message(invalid, base, base, True)
    with pytest.raises(ValueError):
        validate_bridge_message(body, base, base, False)


def test_menu_routes_and_legacy_auto_language(tmp_path, monkeypatch):
    assert workspace_url("http://127.0.0.1:5000", "settings").endswith("/#settings")
    with pytest.raises(ValueError):
        workspace_url("http://127.0.0.1:5000", "../../shell")
    path = tmp_path / "settings.json"
    path.write_text('{"language": null, "language_label": "English"}')
    monkeypatch.setattr(settings, "SETTINGS_PATH", path)
    assert settings.load()["language"] == "auto"
