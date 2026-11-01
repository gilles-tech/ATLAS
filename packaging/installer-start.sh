#!/bin/bash
set -u
HERE="$(cd "$(dirname "$0")/../Resources" && pwd)"
/usr/bin/osascript -e 'display dialog "Installer les fichiers du collecteur réparé ? Python 3 est requis. Arrêtez les anciens processus avant de continuer. La planification restera désactivée jusqu’à validation ; aucune collecte ne sera déclenchée." buttons {"Annuler", "Installer"} default button "Installer" with title "Atlas Marchés — récupération"' >/dev/null 2>&1 || exit 0
/bin/bash "$HERE/install.sh"
CODE=$?
if [ "$CODE" -eq 0 ]; then
  /usr/bin/osascript -e 'display dialog "Fichiers installés. Aucune collecte lancée, aucun LaunchAgent activé. Suivre RECOVERY.md pour les contrôles avant toute planification." buttons {"OK"} with title "Atlas Marchés"' >/dev/null 2>&1
else
  /usr/bin/osascript -e 'display dialog "Installation arrêtée. Consultez ~/AtlasMarches/logs/installer.log. Les processus existants doivent être arrêtés avant installation." buttons {"OK"} with title "Atlas Marchés"' >/dev/null 2>&1
fi
exit "$CODE"
