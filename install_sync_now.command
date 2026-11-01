#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
echo 'Atlas Marchés — installation synchronisation automatique'
bash install_daily_mac.sh
 echo 'Installation terminée. Le premier contrôle de collecte démarre maintenant.'
PY="$(command -v python3)"
nohup "$PY" "$(pwd)/sync_daily.py" >> "$HOME/AtlasMarches/logs/manual-first-sync.log" 2>&1 </dev/null &
echo "Collecte lancée (PID $!). Pour vérifier son état, ouvrir diagnostic_sync.command."
echo 'Vous pouvez fermer cette fenêtre.'
