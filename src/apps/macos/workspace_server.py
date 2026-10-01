"""Own one loopback workspace server for the lifetime of the desktop app."""

import threading
from urllib.parse import urlsplit

from werkzeug.serving import make_server

VIEWS = {"dictation", "dictionary", "scratchpad", "settings"}


def workspace_url(base_url: str, view: str = "dictation") -> str:
    if view not in VIEWS:
        raise ValueError("Unknown workspace view")
    return f"{base_url}/#{view}"


def same_origin(candidate: str, base_url: str) -> bool:
    try:
        parsed, base = urlsplit(candidate), urlsplit(base_url)
        return (parsed.scheme, parsed.hostname, parsed.port) == (
            base.scheme,
            base.hostname,
            base.port,
        )
    except ValueError:
        return False


class WorkspaceServer:
    """Never adopt or terminate another server, even when the preferred port is busy."""

    def __init__(self, application, preferred_port=5000, server_factory=make_server):
        self.application = application
        self.preferred_port = preferred_port
        self._factory = server_factory
        self._server = None
        self._thread = None
        self._lock = threading.RLock()

    @property
    def running(self):
        return bool(self._thread and self._thread.is_alive())

    @property
    def base_url(self):
        if not self.running:
            raise RuntimeError("Workspace server is not running")
        return f"http://127.0.0.1:{self._server.server_port}"

    def start(self):
        with self._lock:
            if self.running:
                return self.base_url
            try:
                server = self._factory(
                    "127.0.0.1", self.preferred_port, self.application, threaded=True
                )
            except (OSError, SystemExit):
                # Reserve a free port atomically, instead of racing an availability probe.
                server = self._factory("127.0.0.1", 0, self.application, threaded=True)
            self._server = server
            self._thread = threading.Thread(
                target=server.serve_forever, name="RoastMyAudioWorkspace", daemon=True
            )
            self._thread.start()
            return self.base_url

    def stop(self):
        with self._lock:
            server, thread = self._server, self._thread
            if server is None:
                return
            if thread and thread.is_alive():
                server.shutdown()
                thread.join(timeout=3)
            server.server_close()
            self._server = None
            self._thread = None

    def restart(self):
        with self._lock:
            self.stop()
            return self.start()
