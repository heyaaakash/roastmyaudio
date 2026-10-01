"""Atomic JSON replacement and reentrant file locks for shared local storage."""

import json
import os
import tempfile
from functools import lru_cache, wraps
from pathlib import Path

from filelock import FileLock


@lru_cache(maxsize=64)
def _lock(path: str) -> FileLock:
    return FileLock(path + ".lock", timeout=15)


def synchronized(path_getter):
    """Hold a shared file lock across a complete read/modify/write operation."""

    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            path = Path(path_getter()).resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            with _lock(str(path)):
                return function(*args, **kwargs)

        return wrapped

    return decorate


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=path.parent, encoding="utf-8", delete=False
    ) as temp:
        temp.write(json.dumps(value, indent=2))
        temporary = Path(temp.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
