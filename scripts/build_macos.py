"""Build and inspect a local native preview; Developer ID/notarization are separate."""

import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    if sys.platform != "darwin":
        raise SystemExit("Build the Mac app on macOS")
    environment = dict(os.environ)
    environment["PYINSTALLER_CONFIG_DIR"] = str(ROOT / "build/pyinstaller-cache")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--distpath",
            str(ROOT / "dist/macos"),
            "--workpath",
            str(ROOT / "build/macos"),
            str(ROOT / "packaging/macos/RoastMyAudio.spec"),
        ],
        cwd=ROOT,
        env=environment,
        check=True,
    )
    app = ROOT / "dist/macos/RoastMyAudio.app"
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
    subprocess.run(["plutil", "-lint", str(app / "Contents/Info.plist")], check=True)
    version = (ROOT / "VERSION").read_text().strip()
    archive = ROOT / f"dist/macos/RoastMyAudio-{version}-{platform.machine()}-preview.zip"
    subprocess.run(
        ["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(app), str(archive)], check=True
    )
    metadata = {
        "version": version,
        "architecture": platform.machine(),
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "dirty": bool(
            subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
        ),
        "signing": "Developer ID requested; inspect before distribution"
        if environment.get("RMA_CODESIGN_IDENTITY")
        else "ad hoc local preview",
        "notarized": False,
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "archive": archive.name,
        "scope": "local developer preview, not published",
    }
    (archive.parent / "BUILD_INFO.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(
        f"Local Mac preview: {app}. Signed ad hoc unless an explicit identity was supplied; not notarized."
    )


if __name__ == "__main__":
    main()
