#!/bin/bash
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$(command -v python3)"
LABEL="fr.atlasmarches.daily-sync"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/AtlasMarches/logs" "$HOME/AtlasMarches/data"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>$LABEL</string>
<key>ProgramArguments</key><array><string>$PYTHON</string><string>$APP_DIR/sync_daily.py</string></array>
<key>StartInterval</key><integer>14400</integer>
<key>RunAtLoad</key><true/>
<key>StandardOutPath</key><string>$HOME/AtlasMarches/logs/daily-sync.log</string>
<key>StandardErrorPath</key><string>$HOME/AtlasMarches/logs/daily-sync-error.log</string>
<key>ProcessType</key><string>Background</string>
</dict></plist>
EOF
plutil -lint "$PLIST"
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Atlas sync configured at login and every 4 hours while session is available."
echo "To run immediately: python3 '$APP_DIR/sync_daily.py'"
echo "Status: $HOME/AtlasMarches/data/sync-status.json"
