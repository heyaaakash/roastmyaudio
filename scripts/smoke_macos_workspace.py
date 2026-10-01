"""Run the source app's native smoke with isolated storage established before imports."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.apps.macos.launcher import main  # noqa: E402

if __name__ == "__main__":
    sys.argv.append("--smoke")
    main()
