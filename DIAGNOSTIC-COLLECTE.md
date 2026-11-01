# Atlas Marchés — diagnostic collecte (31 octobre 2026)

## Constat vérifié dans le code
- 108 200 représente la dernière valeur communiquée par l'utilisateur, pas le résultat d'un nouvel import.
- Le package initial contient **feeds.json = []** : aucun flux RSS/Atom supplémentaire actif.
- `sync_daily.py` et le mode desktop `--sync` n'importaient que BOAMP et TED.
- Le planificateur macOS n'est effectif que si le LaunchAgent a été réellement installé ; la présence du fichier d'installation ne constitue pas une preuve d'exécution.
- BOAMP est borné à 30 pages de 100 avis par défaut, les mêmes enregistrements peuvent être réimportés sans accroître le compteur.
- TED est parcouru en mode ACTIVE ; son résultat effectif dépend du serveur API et des erreurs éventuelles.
- La couverture de 82 sources est **un catalogue**, non 82 connecteurs exécutables.

## Modifications de ce paquet
- Moteur de sync partagé (`sync_engine.py`) utilisé par le lanceur desktop et la tâche quotidienne.
- Écrit `before`, `after`, `new_unique_records`, `delta_by_source`, `duration_seconds`, `status` et erreurs par source.
- Prend en charge les flux RSS/Atom explicitement activés dans `feeds.json`.
- Ne présente pas la synchronisation comme réussie si un connecteur renvoie une erreur structurée.
- Stocke un état à chaque source, pour éviter les rapports silencieux si l'exécution échoue.

## Test sur le Mac
Avec le kit source installé (l'utilisateur final du DMG n'aura pas besoin de Terminal) :

`python3 sync_daily.py`

Lire `~/AtlasMarches/data/sync-status.json` ou, pour l'application desktop, `~/AtlasMarches/data/desktop-sync-status.json`.

Le statut de macOS se vérifie par `launchctl print gui/$(id -u)/fr.atlasmarches.daily-sync` ou le label desktop `fr.atlasmarches.desktop.sync`.

## Périmètre encore non réalisé
- Connecteurs opérationnels des plateformes de défense, santé, finance et pays nationaux au-delà de BOAMP/TED ; l'utilisateur doit les distinguer des sources répertoriées.
- Backfill historique exhaustif et vérification réseau du volume de marchés actuellement ouverts.
- Synchronisation garantie 24/7 sans Mac allumé : nécessite un service cloud.
