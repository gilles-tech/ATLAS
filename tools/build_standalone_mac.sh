#!/bin/bash
# Build Atlas Marchés as a standalone macOS .app/.dmg, with a self-contained Python runtime.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[[ "$(uname -s)" == "Darwin" ]] || { echo "ERROR: macOS required"; exit 1; }
PYTHON="$(command -v python3)"
VENV="$ROOT/.atlas-build-venv"
"$PYTHON" -m venv "$VENV"
"$VENV/bin/python" -m pip install --disable-pip-version-check --upgrade pip
"$VENV/bin/python" -m pip install --disable-pip-version-check "pyinstaller>=6.0,<7" "pywebview>=5,<7"
"$VENV/bin/python" packaging/build.py
APP="$ROOT/dist/AtlasMarches.app"
[[ -d "$APP" ]] || { echo "ERROR: app bundle missing"; exit 1; }
REPORT="$ROOT/release/standalone-self-check.json"
mkdir -p "$ROOT/release"
"$APP/Contents/MacOS/AtlasMarches" --self-check --report "$REPORT"
"$VENV/bin/python" - "$REPORT" <<'PY'
import json,sys
r=json.load(open(sys.argv[1],encoding='utf-8'))
if r.get('status')!='passed':
    raise SystemExit('ERROR: packaged self-check did not pass; release stopped')
print('Standalone acceptance:',r['status'])
PY
ARCH="$(uname -m)"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
cp -R "$APP" "$STAGE/AtlasMarches.app"
ln -s /Applications "$STAGE/Applications"
DMG="$ROOT/release/AtlasMarches-macOS-$ARCH-unsigned.dmg"
hdiutil create -volname "Atlas Marchés" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
shasum -a 256 "$DMG" > "$DMG.sha256"
echo "DONE: $APP"
echo "DONE: $DMG"
echo "CHECK: $REPORT"
echo "Unsigned / not notarized. Does not replace installed collector LaunchAgent."
