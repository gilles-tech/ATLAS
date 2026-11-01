#!/bin/bash
set -euo pipefail
APP="/Applications/AtlasMarches.app/Contents/MacOS/AtlasMarches"
if [[ ! -x "$APP" ]]; then echo "Copy AtlasMarches.app into /Applications first"; exit 1; fi
LABEL=fr.atlasmarches.desktop.sync
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/AtlasMarches/logs"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>$LABEL</string>
<key>ProgramArguments</key><array><string>$APP</string><string>--sync</string></array>
<key>StartCalendarInterval</key><dict><key>Hour</key><integer>6</integer><key>Minute</key><integer>0</integer></dict>
<key>StandardOutPath</key><string>$HOME/AtlasMarches/logs/desktop-sync.log</string>
<key>StandardErrorPath</key><string>$HOME/AtlasMarches/logs/desktop-sync-error.log</string>
</dict></plist>
EOF
plutil -lint "$PLIST"
launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Installed 06:00 daily synchronization while user session is available."
