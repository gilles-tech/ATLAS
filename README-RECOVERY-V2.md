# Atlas Marchés — Recovery v2 : pays TED

La base persistante reste `~/AtlasMarches/data/atlas.db`. Cette mise à jour ne télécharge aucun nouvel avis.

## Procédure

1. Arrêter le serveur Atlas (Ctrl+C).
2. `python3 app.py --normalize-all-countries`
3. `python3 app.py --audit`
4. `python3 app.py --port 8781`

La commande normalise toutes les variantes ISO alpha-3 déjà présentes (DEU → DE, FRA → FR, etc.) et conserve le nombre de lignes exactement. Elle effectue une sauvegarde SQLite atomique avant la modification. Réexécutable : aucune nouvelle modification lors d'une seconde exécution.

Les recherches pays et facettes acceptent les anciennes variantes même avant la migration. Il ne s'agit pas d'un correctif de statut de procédure : les avis expirés ou sans échéance restent distincts. Les 82 sources du catalogue ne sont pas toutes connectées.
