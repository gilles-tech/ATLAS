# Atlas Marchés — Correctif recherche globale

Cette modification concerne la barre « Rechercher mots-clés, CPV, acheteurs et descriptions… » du poste de recherche Atlas, **pas** le filtre du module APProch.

- Index FTS5 local construit à partir des avis déjà présents et entretenu automatiquement lors des nouveaux imports.
- Recherche par concepts avec les synonymes multilingues existants ; filtres pays, source, dates et statuts inchangés.
- Entrée déclenche la recherche immédiatement ; toute saisie relance la requête après 500 ms.
- Si la bibliothèque SQLite ne dispose pas de FTS5, le moteur historique reste disponible.
- La base de production demeure `~/AtlasMarches/data/atlas.db` ; elle n'est pas incluse dans l'archive.
- Lors du premier démarrage, la création de l'index sur 108 000+ avis peut prendre du temps. Les prochains démarrages le conservent.

## Installation

Arrêter l'ancien serveur, extraire le ZIP, se placer dans `atlas-github-release` et lancer `python3 app.py --port 8786`. Ouvrir `http://127.0.0.1:8786/index.html` et actualiser sans cache.

## Vérification

1. Dans le **poste de recherche principal**, chercher `cybersécurité` avec pays Tous.
2. Recommencer avec pays Allemagne ; le résultat doit être un sous-ensemble du précédent.
3. Chercher un terme inexistant ; la liste doit afficher zéro sans planter.
4. Effacer les termes ; les résultats doivent revenir.
5. Vérifier les deux catégories Funding & Tenders et APProch sans régression.

Ce correctif ne déclare pas de nouvelles sources connectées et ne promet pas une traduction universelle : le lexique métier existant couvre les concepts qu'il connaît.
