import sys
import socket
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from werkzeug.serving import make_server

from web_mvp.app import app
from warmup import load_models_async


def _find_open_port(start_port: int = 5000, max_tries: int = 50) -> int:
    for port in range(start_port, start_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("No free local port found for the app server")


class _ServerThread(threading.Thread):
    def __init__(self, host: str, port: int):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.server = make_server(host, port, app)

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()


def main():
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError(
            "pywebview is required. Install with: "
            "/Users/isd0605/Documents/Github/openai-whsiper/.venv/bin/python -m pip install pywebview"
        ) from exc

    port = _find_open_port(5000)
    server_thread = _ServerThread("127.0.0.1", port)
    server_thread.start()

    # Give the local Flask server a moment to boot before opening the window.
    time.sleep(0.5)

    # Start loading models in the background before showing the window
    load_models_async()

    window = webview.create_window(
        "Whisper Dictation",
        f"http://127.0.0.1:{port}",
        width=980,
        height=760,
        min_size=(760, 560),
    )

    try:
        webview.start()
    finally:
        server_thread.shutdown()


if __name__ == "__main__":
    main()
