#!/bin/bash
set -euo pipefail
BASE="$HOME/AtlasMarches"
TARGET="$HOME/Library/Application Support/AtlasMarches/collector"
LOG="$BASE/logs/installer.log"
mkdir -p "$BASE/data" "$BASE/logs" "$HOME/Library/LaunchAgents" "$TARGET"
exec > >(tee -a "$LOG") 2>&1
printf '[%s] Installing Atlas Collector\n' "$(date -u +%FT%TZ)"
RES="$(cd "$(dirname "$0")" && pwd)"
LABEL=fr.atlasmarches.collector
if /bin/launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
  echo 'STOP: unload the existing collector LaunchAgent and confirm its process has stopped before installation.'
  exit 5
fi
if /usr/bin/pgrep -f '[s]ync_daily.py|[r]un-collector.sh' >/dev/null || /usr/bin/pgrep -f "$TARGET/app.py" >/dev/null; then
  echo 'STOP: a collector or installed web process may still be running. Stop it gracefully before replacing source.'
  exit 5
fi
# Avoid overwriting any user database or API secrets
for file in app.py sync_daily.py sync_engine.py collector_runtime.py ted_collector.py maintenance.py ted_check.py approch.py eu_ft.py sources.json buyers.json access_registry.json RECOVERY.md; do
  /bin/cp -f "$RES/$file" "$TARGET/$file"
done
if [ ! -f "$TARGET/feeds.json" ]; then /bin/cp "$RES/feeds.json" "$TARGET/feeds.json"; fi
/bin/mkdir -p "$TARGET/static"
/bin/cp -R "$RES/static/." "$TARGET/static/"
PY=""
for path in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
  if [ -x "$path" ]; then PY="$path"; break; fi
done
if [ -z "$PY" ]; then
  echo 'ERREUR: Python 3 absent. Ce paquet installe le service mais ne contient pas encore un runtime Python embarqué.'
  exit 4
fi
# Persistent command; no reference to Downloads or versioned directories.
cat > "$TARGET/run-collector.sh" <<EOF
#!/bin/bash
cd "$TARGET" || exit 1
exec "$PY" "$TARGET/sync_daily.py"
EOF
/bin/chmod 755 "$TARGET/run-collector.sh"
LABEL=fr.atlasmarches.collector
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PLIST_NEW="$PLIST.new"
# Escape via Python plistlib to generate a well formed plist
"$PY" - "$PLIST_NEW" "$LABEL" "$TARGET/run-collector.sh" "$BASE/logs" <<'PYPLIST'
import plistlib,sys
path,label,runner,logs=sys.argv[1:]
with open(path,'wb') as f:
    plistlib.dump({'Label':label,'ProgramArguments':[runner],
        'StartInterval':14400,'RunAtLoad':False,
        'StandardOutPath':logs+'/collector.log',
        'StandardErrorPath':logs+'/collector-error.log',
        'ProcessType':'Background'},f)
PYPLIST
/usr/bin/plutil -lint "$PLIST_NEW"
/bin/mv -f "$PLIST_NEW" "$PLIST"
echo 'Atlas Collector files installed; scheduling remains unloaded. No collection was started.'
echo 'NO-GO for scheduling until the controlled TED+BOAMP run, database integrity and status/exit-code gates pass.'
