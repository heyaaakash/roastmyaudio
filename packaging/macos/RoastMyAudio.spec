# Native onedir bundle: excludes private runtime data/model weights and developer tools.
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, copy_metadata

root = Path(SPECPATH).parents[1]
version = (root / "VERSION").read_text().strip()
data = [(str(root / "VERSION"), "."), (str(root / "src/apps/web/templates"), "src/apps/web/templates"), (str(root / "src/apps/web/static"), "src/apps/web/static"), (str(root / "LICENSE"), "."), (str(root / "docs/ATTRIBUTIONS.md"), ".")]
for package in ("faster_whisper", "_sounddevice_data", "onnxruntime"):
    data += collect_data_files(package)
for package in ("faster-whisper", "Flask", "sounddevice"):
    data += copy_metadata(package)
binaries = collect_dynamic_libs("ctranslate2") + collect_dynamic_libs("onnxruntime")
a = Analysis([str(root / "src/apps/macos/launcher.py")], pathex=[str(root)], binaries=binaries, datas=data, hiddenimports=["objc", "AppKit", "Foundation", "WebKit", "Quartz", "ApplicationServices", "AVFoundation", "ServiceManagement", "pynput.keyboard._darwin"], hookspath=[], excludes=["pytest", "ruff", "tkinter", "matplotlib", "pandas", "IPython", "notebook"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="RoastMyAudio", debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=False, codesign_identity=os.environ.get("RMA_CODESIGN_IDENTITY"), entitlements_file=str(root / "packaging/macos/entitlements.plist"))
collection = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="RoastMyAudio")
app = BUNDLE(collection, name="RoastMyAudio.app", icon=str(root / "packaging/macos/AppIcon.icns") if (root / "packaging/macos/AppIcon.icns").exists() else None, bundle_identifier="com.heyaaakash.roastmyaudio", version=version, info_plist={"CFBundleShortVersionString": version, "CFBundleVersion": version, "LSUIElement": True, "NSMicrophoneUsageDescription": "RoastMyAudio uses your microphone when you start dictation. Speech is processed on this Mac.", "NSHighResolutionCapable": True, "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True}})
