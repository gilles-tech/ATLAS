# Atlas Marchés — dépôt macOS et builds automatisés

## Ce dépôt contient
Code Python d'Atlas Marchés, interface web, lanceur natif pywebview, synchronisation locale et workflow macOS Apple Silicon / Intel.

## Données privées : IMPORTANT
La base ne doit **jamais** être ajoutée au dépôt. Le fichier utilisateur est `~/AtlasMarches/data/atlas.db`, externe à l'application. Les clés et comptes fournisseurs ne doivent pas être commités. `.gitignore` bloque plusieurs extensions courantes, mais vérifier aussi les commits avant publication.

## Préparer GitHub sans Terminal
1. Sur GitHub, créer un dépôt **privé** nommé `atlas-marches` dans le compte autorisé.
2. Dans GitHub Desktop, utiliser **File > Add Local Repository** puis **Create a Repository** sur ce dossier si nécessaire. Faire le premier commit puis **Publish repository**, en gardant *Keep this code private*.
3. Une fois les fichiers envoyés, GitHub > Actions > `Atlas Marches — macOS DMG` > Run workflow.
4. Après réussite, ouvrir l'exécution > Artifacts > télécharger le DMG Apple Silicon (`arm64`) ou Intel (`x86_64`).

## Avant distribution publique
Les DMG produits par ce workflow sont **non signés** et **non notarisés**. Ne pas les présenter comme un installateur public certifié. Il faut tester l'application sur chaque architecture et configurer un certificat Developer ID Application et la notarisation Apple.

## Vérifications réalisées localement (Linux)
`python3 -m unittest discover -p 'test_*.py' -v` et `python3 -m py_compile app.py desktop.py desktop_autosync.py`.
La compilation DMG ne peut pas être testée dans un environnement Linux et n'est pas prétendue réussie ici.

## Critères d'acceptation
- Ouverture de la fenêtre native sans Python ni Terminal sur machine cible.
- Filtres et résultats consultables ; pays ISO2/ISO3 correctement traités.
- Conservation de `~/AtlasMarches/data/atlas.db` et des favoris après mise à jour.
- Synchronisation à 06:00 installée seulement après accord de l'utilisateur.
- Aucune clé API et aucune base de production dans la release.
- Les portails catalogués ne sont pas confondus avec des connecteurs actifs.
