# État de collecte Atlas

Le compteur seul ne prouve pas que la collecte fonctionne. L’interface montre désormais la dernière date de cycle et les sources en erreur, via `/api/sync-status`.

Pour activer la planification sur macOS, conserver ce dossier à son emplacement définitif puis double-cliquer sur `ACTIVER-SYNCHRO.command`. La tâche macOS pointe vers **ce dossier**. Ne pas le déplacer après installation ; réactiver si le dossier change.

Le collecteur continue de demander les données de BOAMP, TED, APProch, ainsi que Funding & Tenders (appels d'offres et financements séparés). Si une API refuse la requête, le statut doit afficher l'erreur : aucune augmentation de compteur n'est garantie. Un Mac éteint ou en veille peut retarder les cycles.

**Attention** : `feeds.json` est encore vide. Les autres plateformes cataloguées ne sont pas magiquement alimentées. Les données APProch et les financements de l'UE ne sont pas tous comptés dans `opportunities`.
