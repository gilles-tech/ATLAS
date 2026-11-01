#!/bin/bash
# Package an already-built AtlasMarches.app without recompiling or touching the collector.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/dist/AtlasMarches.app"
REPORT="$ROOT/release/standalone-self-check.json"
[[ "$(uname -s)" == "Darwin" ]] || { echo "ERROR: macOS required"; exit 1; }
[[ -d "$APP" ]] || { echo "ERROR: missing $APP"; exit 1; }
[[ -f "$REPORT" ]] || { echo "ERROR: missing self-check report"; exit 1; }
python3 - "$REPORT" <<'PY'
import json, sys
report=json.load(open(sys.argv[1],encoding='utf8'))
if report.get('status')!='passed':
    raise SystemExit('STOP: packaged app has not passed its self-check')
PY
ARCH="$(uname -m)"
OUT="$ROOT/release/AtlasMarches-macOS-$ARCH-unsigned.dmg"
STAGE="$(mktemp -d "${TMPDIR:-/tmp}/atlas-dmg-stage.XXXXXX")"
TEMP_OUT="$(mktemp "${TMPDIR:-/tmp}/atlas-dmg-output.XXXXXX.dmg")"
rm -f "$TEMP_OUT"
cleanup(){ rm -rf "$STAGE"; rm -f "$TEMP_OUT"; }
trap cleanup EXIT
cp -R "$APP" "$STAGE/AtlasMarches.app"
ln -s /Applications "$STAGE/Applications"
# Never overwrite a possibly mounted/in-use previous DMG during creation.
# Create into a unique output file, validate, then move the completed image.
if ! hdiutil create -volname "Atlas Marchés" -srcfolder "$STAGE" -format UDZO "$TEMP_OUT"; then
    echo "ERROR: macOS disk-image creation failed; existing release unchanged."
    exit 1
fi
hdiutil verify "$TEMP_OUT"
if [[ -e "$OUT" ]]; then
    # Preserve prior release rather than forcibly overwriting an in-use disk image.
    OUT="$ROOT/release/AtlasMarches-macOS-$ARCH-unsigned-$(date +%Y%m%d-%H%M%S).dmg"
fi
mv "$TEMP_OUT" "$OUT"
shasum -a 256 "$OUT" > "$OUT.sha256"
echo "DONE: $OUT"
echo "CHECK: $REPORT"
echo "Unsigned / not notarized; local test build only."
