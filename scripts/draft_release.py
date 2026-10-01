"""Upload an explicit draft only, after verifying clean tagged source and hashes."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "heyaaakash/roastmyaudio"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main():
    version = (ROOT / "VERSION").read_text().strip()
    tag = f"v{version}"
    folder = ROOT / "dist" / f"release-{version}"
    commit = git("rev-parse", "HEAD")
    if git("status", "--porcelain") or git("rev-parse", f"{tag}^{{commit}}") != commit:
        raise SystemExit("Draft upload requires clean exact tagged source.")
    info = json.loads((folder / "BUILD_INFO.json").read_text())
    if info["dirty"] or info["commit"] != commit or info["version"] != version:
        raise SystemExit("Build provenance does not match release source.")
    assets = [
        folder / f"roastmyaudio-{version}-source.zip",
        folder / "BUILD_INFO.json",
        folder / "RELEASE_NOTES.md",
        folder / "SHA256SUMS.txt",
    ]
    expected = {path.name for path in assets[:-1]}
    entries = {}
    for line in assets[-1].read_text().splitlines():
        digest, name = line.split("  ", 1)
        entries[name] = digest
    if set(entries) != expected:
        raise SystemExit("Checksum manifest must match the exact explicit asset list.")
    for path in assets[:-1]:
        if hashlib.sha256(path.read_bytes()).hexdigest() != entries[path.name]:
            raise SystemExit(f"Hash mismatch: {path.name}")
    remote = git("ls-remote", "origin", f"refs/tags/{tag}^{{}}", f"refs/tags/{tag}")
    if commit not in {line.split()[0] for line in remote.splitlines()}:
        raise SystemExit("Remote tag does not identify the staged source.")
    # A successful lookup refuses overwrite. Creation also refuses an existing release.
    existing = subprocess.run(["gh", "release", "view", tag, "--repo", REPO], capture_output=True)
    if existing.returncode == 0:
        raise SystemExit("Release already exists. Refusing overwrite.")
    subprocess.run(
        [
            "gh",
            "release",
            "create",
            tag,
            "--repo",
            REPO,
            "--draft",
            "--prerelease",
            "--verify-tag",
            "--title",
            f"RoastMyAudio {version} · source preview",
            "--notes-file",
            str(folder / "RELEASE_NOTES.md"),
            *map(str, assets),
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
