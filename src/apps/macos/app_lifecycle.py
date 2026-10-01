"""Single-instance ownership and non-destructive source-data import."""

import json
import shutil
from pathlib import Path

from filelock import FileLock, Timeout

from src.shared.storage import write_json


class AppInstance:
    def __init__(self, data_dir):
        self.path = Path(data_dir)
        self.path.mkdir(parents=True, exist_ok=True)
        self.lock = FileLock(str(self.path / "desktop-instance.lock"), timeout=0)

    def acquire(self):
        try:
            self.lock.acquire()
            return True
        except Timeout:
            return False

    def release(self):
        self.lock.release()


def import_source_data(source, destination):
    """Copy known data only into an empty destination; keep original data untouched."""
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve() or not source.is_dir():
        return False
    destination.mkdir(parents=True, exist_ok=True)
    with FileLock(str(destination / "source-import.lock")):
        marker = destination / "source-import.json"
        if marker.exists() or any(
            (destination / name).exists()
            for name in ("history.json", "settings.json", "workspace.json", "dictionary.json", "personalization.json")
        ) or any((destination / "recordings").glob("*.wav")):
            return False
        pending = {}
        for name in (
            "history.json",
            "settings.json",
            "dictionary.json",
            "workspace.json",
            "personalization.json",
        ):
            file = source / name
            if file.is_file():
                if file.is_symlink():
                    continue
                try:
                    pending[name] = json.loads(file.read_text())
                except (OSError, ValueError):
                    # Leave all original files untouched and do not import partial JSON.
                    return False
        for name, value in pending.items():
            write_json(destination / name, value)
        recordings = source / "recordings"
        if recordings.is_dir():
            target = destination / "recordings"
            target.mkdir(exist_ok=True)
            for file in recordings.glob("*.wav"):
                if file.is_file() and not file.is_symlink() and not (target / file.name).exists():
                    shutil.copy2(file, target / file.name)
        write_json(marker, {"completed": True})
        return True


def request_reopen(data_dir):
    write_json(Path(data_dir) / "desktop-reopen.json", {"requested": True})


def consume_reopen(data_dir):
    path = Path(data_dir) / "desktop-reopen.json"
    with FileLock(str(path) + ".lock"):
        if not path.exists():
            return False
        path.unlink()
        return True
