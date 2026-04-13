#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# RoastMyAudio — Install / Uninstall launchd login-item
#
# Usage:
#   bash scripts/install_launch_agent.sh         # install auto-start
#   bash scripts/install_launch_agent.sh remove  # remove auto-start
#
# This creates a plist in ~/Library/LaunchAgents/ that starts RoastMyAudio
# automatically at login. Nothing is installed outside your home directory.
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

LABEL="com.roastmyaudio.app"
PLIST_PATH="$HOME/Library/LaunchAgents/${LABEL}.plist"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"
ENTRY_POINT="$PROJECT_ROOT/src/apps/macos/menubar_dictation.py"
LOG_DIR="$PROJECT_ROOT/data/logs"

# ─── Remove ───────────────────────────────────────────────────────────────────
if [[ "${1:-}" == "remove" ]]; then
    if launchctl list | grep -q "$LABEL"; then
        launchctl unload "$PLIST_PATH" 2>/dev/null || true
        echo "→ Unloaded $LABEL"
    fi
    if [[ -f "$PLIST_PATH" ]]; then
        rm "$PLIST_PATH"
        echo "→ Removed $PLIST_PATH"
    fi
    echo "✓ RoastMyAudio auto-start removed."
    exit 0
fi

# ─── Preflight checks ─────────────────────────────────────────────────────────
if [[ ! -f "$VENV_PYTHON" ]]; then
    echo "Error: virtual environment not found at $VENV_PYTHON"
    echo "Run 'make setup' first."
    exit 1
fi

if [[ ! -f "$ENTRY_POINT" ]]; then
    echo "Error: entry point not found at $ENTRY_POINT"
    exit 1
fi

mkdir -p "$LOG_DIR"

# ─── Write plist ──────────────────────────────────────────────────────────────
cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${VENV_PYTHON}</string>
        <string>${ENTRY_POINT}</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <false/>

    <key>StandardOutPath</key>
    <string>${LOG_DIR}/roastmyaudio.log</string>

    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/roastmyaudio.error.log</string>

    <key>WorkingDirectory</key>
    <string>${PROJECT_ROOT}</string>

    <!-- Throttle restart: wait 10s before relaunching if it crashes -->
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
PLIST

# ─── Load the agent ───────────────────────────────────────────────────────────
# Unload existing instance if present (avoids duplicate)
if launchctl list | grep -q "$LABEL"; then
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
fi

launchctl load "$PLIST_PATH"

echo ""
echo "✓ RoastMyAudio will now start automatically at login."
echo ""
echo "  Plist:    $PLIST_PATH"
echo "  Logs:     $LOG_DIR/roastmyaudio.log"
echo "  Errors:   $LOG_DIR/roastmyaudio.error.log"
echo ""
echo "  To remove auto-start:"
echo "    bash scripts/install_launch_agent.sh remove"
echo ""
