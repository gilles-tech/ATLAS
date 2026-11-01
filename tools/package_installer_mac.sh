#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/dist/AtlasMarches.app"
REPORT="$ROOT/release/standalone-self-check.json"
[[ "$(uname -s)" == "Darwin" ]] || { echo "STOP: macOS only"; exit 1; }
[[ -d "$APP" && -f "$REPORT" ]] || { echo "STOP: build and self-check app first"; exit 1; }
python3 - "$REPORT" <<'PY'
import json,sys
assert json.load(open(sys.argv[1]))['status']=='passed', 'Standalone acceptance must pass'
PY
APP_ID="$(printenv ATLAS_APP_SIGN_IDENTITY || true)"
INSTALLER_ID="$(printenv ATLAS_INSTALLER_SIGN_IDENTITY || true)"
PROFILE="$(printenv ATLAS_NOTARY_PROFILE || true)"
if [[ -n "$APP_ID" ]]; then
  codesign --force --deep --options runtime --timestamp --sign "$APP_ID" "$APP"
  codesign --verify --deep --strict "$APP"
elif [[ -n "$INSTALLER_ID" || -n "$PROFILE" ]]; then
  echo "STOP: app Developer ID signature required"; exit 1
fi
[[ -z "$PROFILE" || -n "$INSTALLER_ID" ]] || { echo "STOP: Installer Developer ID signature required"; exit 1; }
mkdir -p "$ROOT/release"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
productbuild --component "$APP" /Applications "$TMP/unsigned.pkg"
CANDIDATE="$TMP/unsigned.pkg"
if [[ -n "$INSTALLER_ID" ]]; then
  productsign --sign "$INSTALLER_ID" "$CANDIDATE" "$TMP/signed.pkg"
  CANDIDATE="$TMP/signed.pkg"
  pkgutil --check-signature "$CANDIDATE"
fi
if [[ -n "$PROFILE" ]]; then
  xcrun notarytool submit "$CANDIDATE" --keychain-profile "$PROFILE" --wait
  xcrun stapler staple "$CANDIDATE"
  xcrun stapler validate "$CANDIDATE"
fi
OUT="$ROOT/release/AtlasMarches-Installer-$(uname -m)-$(date +%Y%m%d-%H%M%S).pkg"
cp "$CANDIDATE" "$OUT"
shasum -a 256 "$OUT" > "$OUT.sha256"
echo "INSTALLER: $OUT"
[[ -n "$PROFILE" ]] || echo "TEST-ONLY: package not notarized; macOS may warn or block."
echo "Does not touch existing Atlas database or collector scheduling."
