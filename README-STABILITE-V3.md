# Atlas Marchés – stabilité de navigation v3

## Corrections
- Un seul gestionnaire des changements de vue (suppression du deuxième écouteur concurrent).
- Un clic sur l’onglet déjà actif ne réinitialise plus la pagination.
- L’interrogation des tâches TED continue toutes les 4 secondes, sans recréer la page ni réinitialiser la recherche.
- Le rafraîchissement de compteurs ne vide pas la liste des avis pendant une requête.
- La position verticale est restaurée après un vrai rechargement du navigateur (mémoire de session, au mieux).

## Données
La base reste `~/AtlasMarches/data/atlas.db`, inchangée. Les 108 200 avis restent dans la base existante ; aucune nouvelle ingestion n’est requise.

## Démarrage
```bash
cd ~/Downloads
unzip -o atlas-marches-stable-v3.zip
cd atlas-marches-stable-v3
python3 app.py --port 8782
```
Ouvrir http://127.0.0.1:8782/index.html.

## Tests manuels indispensables
1. Effectuer une recherche et défiler jusqu’à un avis.
2. Laisser TED synchroniser au moins 30 s : l’onglet, les filtres et le défilement doivent rester identiques.
3. Changer volontairement d’onglet puis revenir.
4. Vérifier les nouvelles données avec une recherche explicite.

Les causes d’un éventuel rechargement complet au niveau du navigateur restent à diagnostiquer à l’aide des journaux réseau/console.
