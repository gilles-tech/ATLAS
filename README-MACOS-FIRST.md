# Atlas Marchés — macOS first build

## Build on your Mac

1. Extract this ZIP to Downloads.
2. Open Terminal and run:

```bash
cd ~/Downloads/atlas-marches-stable-v3
bash build_macos.command
```

3. Find `dist/AtlasMarches-macOS-unsigned.dmg` and mount it. Drag `AtlasMarches.app` into Applications.
4. This is **unsigned / unnotarized**, for private testing. macOS Gatekeeper may block launch. The intended production release must be signed/notarized with an Apple Developer ID (never disable system-wide Gatekeeper).
5. To enable daily sync for this desktop build:

```bash
bash install_daily_desktop_mac.command
```

**Critical**: if the prior Python daily sync LaunchAgent is already installed, disable it first to avoid duplicate jobs:

```bash
launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/fr.atlasmarches.daily-sync.plist" 2>/dev/null || true
```

The SQLite database remains at `~/AtlasMarches/data/atlas.db`. The build does not package a database and never resets it. Do not run import and desktop jobs concurrently while testing.

## Validation status

Python source compilation was tested in the authoring environment. Native DMG build, Apple signing/notarization, on-device GUI and macOS scheduled job must be verified on a Mac. A ZIP of source/build scripts is **not** a prebuilt native installer.
