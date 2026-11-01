# Atlas Marchés 0.7 — intégrations et couverture

**Sources actives dans le code** : BOAMP, TED. Leur fonctionnement réel dépend de l’API et doit être vérifié sur votre Mac.
**Nouveau** : moteur générique RSS/Atom configurable dans `feeds.json`, désactivé par défaut. Ajouter uniquement des URLs de flux officiels **vérifiées**. Aucun scraping HTML et aucun contournement de connexion.
**Catalogue** : plateformes nationales, territoriales, défense, santé, recherche, centrales d’achat, institutions européennes et internationales. Entrée catalogue != connexion active.
**Acheteurs** : surveillance par variantes des noms sur avis indexés (CDC, Bpifrance, Banque de France, etc.).

## Installer
`python3 app.py --port 8771` puis ouvrir http://127.0.0.1:8771/index.html.

## Diagnostic
- `/api/coverage` — nombre d'avis par source/pays/statut ; plateformes non connectées
- `/api/connectors` — adaptateurs codés et dernières exécutions
- `/api/feeds` — flux configurés
- `/api/diagnostics/countries` — contrôles pays TED

## Brancher un flux RSS/Atom public
Créer `feeds.json` à partir de `feeds.example.json`, mettre URL officielle, identifiant stable, pays ISO-2 et `enabled: true`. Exemple URL fictive **à remplacer**.
Puis `python3 app.py --ingest IDENTIFIANT_SOURCE`. Les avis sans échéance restent à vérifier.

## Limites et conformité
TED ne contient pas tous les marchés infraseuils. Les portails authentifiés (achats de banques, certaines plateformes de défense, ECEPP, etc.) ne sont PAS automatiquement ingérés. Les acheteurs ne sont pas des flux. Vérifier droits de réutilisation et robots avant tout adaptateur. Ne jamais afficher « ouvert » si l'échéance n'a pas été vérifiée. La normalisation des lots et pays à partir d'eForms complets reste à améliorer.
