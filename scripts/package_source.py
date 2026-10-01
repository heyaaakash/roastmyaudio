"""Build and re-extract an allowlisted source archive; never includes local audio."""

import hashlib
import json
import platform
import re
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from importlib.metadata import distributions
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCLUDED_DIRS = {"src", "config", "scripts", "docs", "tests", "screenshots", ".github", "packaging"}
INCLUDED_FILES = {
    "README.md",
    "LICENSE",
    "VERSION",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "AGENTS.md",
    "CODE_OF_CONDUCT.md",
    "Makefile",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    ".gitignore",
    ".gitattributes",
}


def source_paths():
    suffixes = {
        ".py",
        ".md",
        ".sh",
        ".cjs",
        ".js",
        ".css",
        ".html",
        ".svg",
        ".png",
        ".toml",
        ".spec",
        ".plist",
        ".icns",
        ".txt",
    }
    candidates = [ROOT / name for name in INCLUDED_FILES]
    for name in INCLUDED_DIRS:
        candidates.extend((ROOT / name).rglob("*"))
    for path in sorted(set(candidates)):
        relative = path.relative_to(ROOT)
        if any(
            part in {"__pycache__", "runtime", ".pytest_cache", ".ruff_cache", "workflows"}
            for part in relative.parts
        ):
            continue
        if path.name.startswith(".env"):
            continue
        if (
            path.is_file()
            and not path.is_symlink()
            and (path.suffix in suffixes or str(relative) in INCLUDED_FILES)
        ):
            yield path


def main():
    version = (ROOT / "VERSION").read_text().strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit("Invalid VERSION")
    destination = ROOT / "dist" / f"release-{version}"
    if destination.exists():
        raise SystemExit(
            f"Staging already exists: {destination}. Review and remove it explicitly before rebuilding."
        )
    paths = list(source_paths())
    # Build inputs are allowlisted; known credential signatures fail without printing values.
    signature = re.compile(
        rb"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY|ghp_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{32,}|AKIA[A-Z0-9]{16}"
    )
    for path in paths:
        if path.suffix in {
            ".py",
            ".md",
            ".txt",
            ".json",
            ".toml",
            ".spec",
            ".plist",
            ".icns",
            ".sh",
            ".js",
            ".cjs",
            ".html",
        } and signature.search(path.read_bytes()):
            raise SystemExit(
                f"Potential credential in {path.relative_to(ROOT)}. Review before packaging."
            )
    destination.mkdir(parents=True)
    artifact = destination / f"roastmyaudio-{version}-source.zip"
    prefix = f"roastmyaudio-{version}"
    with zipfile.ZipFile(artifact, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, f"{prefix}/{path.relative_to(ROOT).as_posix()}")
    with tempfile.TemporaryDirectory() as temporary:
        with zipfile.ZipFile(artifact) as archive:
            assert archive.testzip() is None
            archive.extractall(temporary)
        for path in paths:
            extracted = Path(temporary) / prefix / path.relative_to(ROOT)
            assert extracted.read_bytes() == path.read_bytes(), f"Extraction mismatch: {path}"
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(
        subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
    )
    info = {
        "product": "RoastMyAudio",
        "version": version,
        "commit": commit,
        "dirty": dirty,
        "scope": "source-only",
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "system": platform.platform(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "signing": "N/A: source archive",
        "dependencies": sorted(
            f"{item.metadata['Name']}=={item.version}" for item in distributions()
        ),
        "verification": "Archive extracted and every file byte-compared; this does not validate live dictation.",
    }
    (destination / "BUILD_INFO.json").write_text(json.dumps(info, indent=2) + "\n")
    (destination / "RELEASE_NOTES.md").write_text((ROOT / "docs" / "RELEASE_NOTES.md").read_text())
    assets = [artifact, destination / "BUILD_INFO.json", destination / "RELEASE_NOTES.md"]
    (destination / "SHA256SUMS.txt").write_text(
        "".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in assets
        )
    )
    print(
        f"Validated {len(paths)} source files: {artifact}\nDirty source: {dirty}. Only clean tagged source is eligible for a release draft."
    )


if __name__ == "__main__":
    main()
