# Atlas 0.8.3 — réparation de l’interface résultats

Le diagnostic du 31 octobre 2026 montrait 107 100 avis indexés sans résultats visibles. La cause confirmée : les nœuds HTML `wb-results` et `wb-count` manquaient, alors que le moteur JS les utilise. Cette version les rétablit.

## Installation
1. Arrêter le serveur actuel (Ctrl+C).
2. Extraire le ZIP dans `~/Downloads`.
3. Depuis `~/Downloads/atlas-marches-mvp-v0.8.3`, lancer `python3 app.py --port 8775`.
4. Ouvrir http://127.0.0.1:8775/index.html.

La migration précédente est conservée et réexécutée par le programme sur les anciennes bases. Ne déplacez ni ne supprimez les dossiers précédents avant vérification des compteurs. Aucune base SQLite préremplie n'est incluse dans l'archive.

## Vérification
- `/api/stats` doit retourner un nombre d'avis non nul si les anciennes bases sont accessibles.
- `/api/opportunities?stage=all` doit retourner des données si des avis existent.
- `/api/facets` doit exposer les pays réellement stockés.
- La page doit afficher les cartes et le nombre de résultats. Le filtre « Tous » doit être utilisé pour vérifier la présence d'avis avant « Ouverts confirmés ».

Un nombre d'avis total ne signifie pas que ces avis sont tous ouverts, géolocalisés ou correctement qualifiés. Les pays `UNKNOWN` restent possibles.
