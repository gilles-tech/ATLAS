# Atlas Marchés — installable desktop packaging (macOS / Windows)

## What is included
- Native application entry point `desktop.py` with embedded Python server and a native pywebview window.
- Existing core `app.py`, assets, source registry and persistent database path unchanged.
- PyInstaller build script, macOS .dmg generation and Windows Inno Setup installer script.
- GitHub Actions workflow to compile on hosted macOS Apple Silicon and Windows x64 runners.

## Build locally on macOS or Windows
```bash
python -m pip install -r requirements-desktop.txt
python packaging/build.py
```
This creates `dist/AtlasMarches.app` on macOS or `dist/AtlasMarches/AtlasMarches.exe` on Windows. The output includes Python and project assets. Windows needs the system WebView2 runtime; most supported Windows installations have it, but verify on a clean machine.

## Create installers
Push this directory to a repository and use the `Build Atlas Marches desktop installers` workflow under GitHub Actions. Download the generated artifacts from the completed workflow.

## Data
The application's SQLite database remains in `~/AtlasMarches/data/atlas.db` on macOS and `%USERPROFILE%\\AtlasMarches\\data\\atlas.db` on Windows. No data directory is included in the installers. An existing Mac database is preserved. Windows does not automatically transfer the Mac database.

## Synchronization
The desktop binary accepts `--sync`. The daily macOS launchd script in this source archive belongs to the legacy Python installation and is **not** automatically installed by the desktop package. Schedule `AtlasMarches --sync` via launchd/Windows Task Scheduler for daily jobs on machines that remain available. For guaranteed 24/7 ingestion and shared data across computers, run collectors on a server, not client devices.

## Release gates
These are **build recipes**, not ready-made installers. macOS notarization/Developer ID signing, Windows Authenticode signing, clean-machine smoke tests, runtime fetch tests, Windows WebView2 checks, auto-update infrastructure and installer signing still need completion before public distribution. The source connector coverage remains unchanged: BOAMP/TED and configured feeds, not all catalog sources.
