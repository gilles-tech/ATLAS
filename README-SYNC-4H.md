# Atlas Marchés — vérification et programmation réelle

Ce paquet contient l'application complète et deux fichiers double-cliquables sur macOS :

- `install_sync_now.command` : configure un LaunchAgent pour lancer la collecte à l'ouverture de session et toutes les quatre heures. Une première collecte est également déclenchée au lancement de cette commande. **Ne pas relancer plusieurs fois sans nécessité.**
- `diagnostic_sync.command` : affiche l'état du planificateur et les résultats des collectes.

## Conditions et limites

- Installer dans un dossier permanent (pas dans un dossier temporaire), sinon launchd conserverait un chemin devenu invalide.
- Le Mac doit être allumé, et la session utilisateur disponible ; ce n'est pas une collecte cloud 24/7.
- Les collectes TED étendues peuvent durer plus de quatre heures ; un verrou empêche les collectes simultanées.
- L'augmentation du total n'est pas garantie : seuls les nouveaux identifiants font augmenter le compteur.
- Le collecteur actuel interroge BOAMP et TED. Aucun troisième connecteur n'est activé dans `feeds.json`, qui est vide. Les 82 entrées du catalogue ne constituent pas 82 sources opérationnelles.
- La tâche ne résout pas l'absence de nouvelles offres si une API rejette les requêtes. Lire le statut et les erreurs par source dans le diagnostic.

## Sécurité données

La base reste `~/AtlasMarches/data/atlas.db`. Ne la supprimer ni la committer. Le script de diagnostic ne modifie aucune donnée.
