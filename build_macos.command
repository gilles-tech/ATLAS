#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ "$(uname -s)" != "Darwin" ]]; then echo "This build must run on a Mac"; exit 1; fi
if ! command -v python3 >/dev/null; then echo "Python 3 required on the BUILD Mac (not required for end users)"; exit 1; fi
python3 -m venv .build-venv
.build-venv/bin/python -m pip install --upgrade pip
.build-venv/bin/python -m pip install -r requirements-desktop.txt
.build-venv/bin/python packaging/build.py
APP="$PWD/dist/AtlasMarches.app"
test -d "$APP" || { echo "App build missing"; exit 1; }
mkdir -p dist/dmg-content
ln -sfn /Applications dist/dmg-content/Applications
cp -R "$APP" dist/dmg-content/
hdiutil create -volname "Atlas Marchés" -srcfolder dist/dmg-content -ov -format UDZO dist/AtlasMarches-macOS-unsigned.dmg
echo "DONE: $PWD/dist/AtlasMarches-macOS-unsigned.dmg"
echo "Unsigned local test build. Not notarized for public distribution."
