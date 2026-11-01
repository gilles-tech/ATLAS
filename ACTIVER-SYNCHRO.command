#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
echo "Atlas Marchés — activation de la collecte toutes les quatre heures"
bash install_daily_mac.sh
printf '\nSynchronisation activée. Lire le statut dans Atlas, section État de collecte.\n'
read -r -p "Appuyer sur Entrée pour fermer cette fenêtre..." _ || true
