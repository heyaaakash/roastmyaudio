"""Check release metadata, local documentation links, and sensitive source inputs."""

import re
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
version = (ROOT / "VERSION").read_text().strip()
assert re.fullmatch(r"\d+\.\d+\.\d+", version), "VERSION must be semantic version x.y.z"
manifest = tomllib.loads((ROOT / "pyproject.toml").read_text())
assert "version" in manifest["project"]["dynamic"], "Use VERSION rather than duplicate metadata"
assert not list((ROOT / ".github" / "workflows").glob("*.y*ml")), (
    "Local mode forbids Actions workflows"
)
files = [
    ROOT / "README.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "SECURITY.md",
    *ROOT.glob("docs/*.md"),
]
errors = []
for file in files:
    for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", file.read_text()):
        if target.startswith(("https://", "http://", "#", "mailto:")):
            continue
        path = (file.parent / target.split("#")[0]).resolve()
        if not path.exists():
            errors.append(f"{file.relative_to(ROOT)}: missing {target}")
assert not errors, "\n".join(errors)
assert not list((ROOT / "src").rglob("*.wav")), "Runtime audio must stay out of source"
print(f"Metadata and local documentation links passed (v{version}).")
