# macOS Desktop Apps

This folder now includes two app modes:
- `main.py`: opens the existing web MVP in a native window
- `menubar_dictation.py`: menubar app with global hotkey and type-into-any-app workflow

## Menubar Dictation Mode

### What it does
- Adds a menu bar icon (`W` idle, `R` recording)
- Includes menu action `Open macOS Permissions` for quick setup
- Registers a global push-to-talk hotkey: hold `Fn`
- Recording starts on key hold and stops on release
- If `Fn` is not exposed by macOS input APIs, it automatically falls back to hold `Ctrl+Option+D`
- Shows a pill-style overlay HUD while recording (bottom-center)
- Shows low-latency live preview (few rolling words) in the overlay while speaking
- Includes `Test Overlay (2s)` menu item to verify HUD behavior
- Transcribes with selected Whisper model
- Applies your post-processing formatter
- Pastes the text into whichever app currently has focus
- Menu options:
	- `Copy Last Processed Speech`
	- `Paste Last Processed Speech`

### Runtime storage
All app runtime artifacts are stored in this folder:
- `macos_app/runtime/last_recording.wav`
- `macos_app/runtime/last_processed.txt`

## Setup

activate venv
```bash
source .venv/bin/Activate
```

```bash
cd /Users/isd0605/Documents/Github/openai-whsiper
/Users/isd0605/Documents/Github/openai-whsiper/.venv/bin/python -m pip install pywebview
/Users/isd0605/Documents/Github/openai-whsiper/.venv/bin/python -m pip install -r macos_app/requirements.txt
```

## Run Menubar App

```bash
cd /Users/isd0605/Documents/Github/openai-whsiper
/Users/isd0605/Documents/Github/openai-whsiper/.venv/bin/python macos_app/menubar_dictation.py
```

## Run Webview Wrapper

```bash
cd /Users/isd0605/Documents/Github/openai-whsiper
/Users/isd0605/Documents/Github/openai-whsiper/.venv/bin/python macos_app/main.py
```

## Notes
- This is a development MVP, not a signed `.app` bundle yet.
- For menubar dictation, macOS will ask for permissions:
	- Microphone
	- Accessibility (to type into other apps)
	- Input Monitoring (for global hotkey in some setups)
- After granting permissions, fully quit and relaunch the app.
