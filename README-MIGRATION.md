# v0.8.2 — réparation de la migration historique

**Cause du zéro avis en v0.8.1** : l’archive précédente incluait à tort `.history-merged`. Le premier démarrage sautait l'import. L’archive v0.8.2 exclut cet état et relance la fusion à chaque démarrage. Les anciens `atlas.db` ne sont ni supprimés ni modifiés.

1. Arrêter tous les anciens serveurs Atlas pour finaliser leurs fichiers SQLite WAL.
2. Décompresser le ZIP dans `~/Downloads`.
3. `cd ~/Downloads/atlas-marches-mvp-v0.8.2`
4. `python3 app.py --merge-history` — affiche le chemin de la base active, les bases candidates, les comptes et le bilan de fusion.
5. `python3 app.py --port 8774` puis ouvrir `http://127.0.0.1:8774/index.html`.

L'absence de base candidate ou des comptes à zéro signifie que les avis ne se trouvent pas dans ces dossiers. Ne pas déclencher d’ingestion pour masquer une migration échouée. Vérifier où se trouve le fichier `atlas.db` original, sans remplacer ni effacer les données.
