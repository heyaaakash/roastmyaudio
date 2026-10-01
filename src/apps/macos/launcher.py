"""Source/frozen entry point: establish durable storage before importing the app."""

import multiprocessing
import os
import sys
import tempfile
from pathlib import Path

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ["RMA_DESKTOP"] = "1"


def main():
    # Frozen Python helper processes must not re-enter the menu application.
    multiprocessing.freeze_support()
    if "--smoke" in sys.argv or "--model-smoke" in sys.argv:
        with tempfile.TemporaryDirectory(prefix="rma-desktop-smoke-") as temporary:
            os.environ["RMA_DATA_HOME"] = str(Path(temporary) / "data")
            os.environ.setdefault("RMA_CACHE_HOME", str(Path(temporary) / "cache"))
            from src.apps.macos.menubar_dictation import main as run

            run()
    else:
        from src.apps.macos.menubar_dictation import main as run

        run()


if __name__ == "__main__":
    main()
