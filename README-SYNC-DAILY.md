# Synchronisation quotidienne macOS

Le serveur web et la collecte sont **deux processus différents**. La v3 initiale ne planifiait pas l'ingestion. Ce package ajoute une tâche macOS `launchd`, exécutée à 06:00 en session ouverte. `launchd` peut décaler le lancement après une mise en veille ; il ne garantit pas l'exécution si le Mac est éteint. Ce n'est pas une solution serveur 24/7.

## Installation

```bash
cd ~/Downloads/atlas-marches-stable-v3
bash install_daily_mac.sh
```

## Premier lancement immédiat (peut être long)

```bash
python3 sync_daily.py
```

La synchronisation tente BOAMP puis la pagination TED `ACTIVE`. Elle écrit dans la base persistante `~/AtlasMarches/data/atlas.db`. Les nouveaux avis sont insérés, les avis existants actualisés par identifiant. Un verrou empêche deux exécutions **du script de synchronisation** en parallèle. Les synchronisations manuelles lancées hors du script ne sont pas protégées par ce verrou.

## Suivi

```bash
cat ~/AtlasMarches/data/sync-status.json
cat ~/AtlasMarches/logs/daily-sync.log
tail -50 ~/AtlasMarches/logs/daily-sync-error.log
launchctl print gui/$(id -u)/fr.atlasmarches.daily-sync
```

## Désactivation

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/fr.atlasmarches.daily-sync.plist
rm ~/Library/LaunchAgents/fr.atlasmarches.daily-sync.plist
```

## Limites importantes

- BOAMP : l'adaptateur présent conserve 30 pages de 100 avis par exécution par défaut. Les mêmes avis peuvent être mis à jour, sans accroître le total. L'historique complet nécessite un autre moteur de collecte.
- TED : itère jusqu'à épuisement des résultats `ACTIVE` de la requête ; cela ne prouve pas la couverture de tous les portails européens nationaux.
- Les 82 sources du catalogue ne sont pas 82 connecteurs actifs. Seuls BOAMP et TED sont traités ici.
- La récupération peut prendre longtemps et être interrompue par la veille ou l'arrêt de l'ordinateur. Les pages TED déjà enregistrées sont persistées pendant la collecte.
- Le mécanisme existant peut traiter comme « ouverts » des avis dont le statut est incertain ; vérifier les échéances sur l'avis officiel.
- Aucun secret TED n'est nécessaire pour TED Search API.
