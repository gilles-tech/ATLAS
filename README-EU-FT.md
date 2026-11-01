# Atlas — EU Funding & Tenders (intégration initiale)

## Ce qui est codé
- API officielle SEDIA POST multipart (`query`, `languages`, `displayLanguage`) avec les codes documentés.
- Catégories **tenders** et **grants**, stockées dans une table `eu_ft_calls` distincte de TED/BOAMP.
- Recherche et affichage dans le panneau **Europe — Funding & Tenders** en bas de l’interface.
- API locale `/api/eu-ft?kind=tenders`, `/api/eu-ft?kind=grants`, `/api/eu-ft/stats`.
- POST `/api/eu-ft/ingest` avec `{"kind":"tenders"}` ou `{"kind":"grants"}`.
- Synchronisation incluse dans le cycle automatique `sync_daily.py` / `sync_engine.py`.
- Dédoublonnage par référence officielle et historique des exécutions.

## Limites honnêtes
- Le schéma de retour réel de SEDIA ne peut pas être confirmé par les seuls tests simulés : si la réponse diffère, le connecteur renvoie une erreur **sans créer de faux dossiers**.
- Import plafonné volontairement à 5 pages de 100 par catégorie et par cycle, configurable via `ATLAS_EU_FT_PAGES` (1 à 1000). Ce n'est pas une collecte exhaustive.
- L'API fonctionne avec la valeur publique `apiKey=SEDIA`, **sans clé privée**.
- Les modules « partenaires », « projets », « organisations », « facettes enrichies » restent à intégrer après vérification de leurs formats réels. Ne pas les compter comme actifs.
- Les compteurs existants BOAMP/TED sont inchangés ; les financements ne sont pas mélangés aux appels d'offres.

## Démarrage Mac (en conservant les données)
Décompresser le ZIP, puis lancer `app.py` sur un port libre, ou reprendre le mécanisme desktop existant. Base persistante : `~/AtlasMarches/data/atlas.db`.
Pour déclencher le cycle, lancer `python3 sync_daily.py` depuis le dossier de l'application ; le scheduler macOS déjà installé doit pointer vers **ce** nouveau dossier si l'on veut inclure EU FT dans les prochaines exécutions automatiques.

## Diagnostics
- `http://127.0.0.1:8785/api/eu-ft/stats`
- `~/AtlasMarches/data/sync-status.json`
- `diagnostic_sync.command` si le kit installé sur Mac est conservé.

**Important :** les deux scripts `.command` déclarés exécutés par l’utilisateur sont pris en compte, mais leur succès doit être vérifié via les journaux. Ils peuvent encore pointer sur l’ancien dossier.
