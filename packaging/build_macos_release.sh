#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ "$(uname -s)" == 'Darwin' ]] || { echo 'A macOS runner is required'; exit 1; }
python3 packaging/build.py
APP="$PWD/dist/AtlasMarches.app"
[[ -d "$APP" ]] || { echo 'Missing built .app'; exit 1; }
ARCH="$(uname -m)"
mkdir -p release
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
cp -R "$APP" "$STAGE/AtlasMarches.app"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname 'Atlas Marchés' -srcfolder "$STAGE" -ov -format UDZO "release/AtlasMarches-macOS-${ARCH}-unsigned.dmg"
echo "Built release/AtlasMarches-macOS-${ARCH}-unsigned.dmg"
