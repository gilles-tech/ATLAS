# Atlas v0.5.2 — correctif France = 0

Corrections : mise à jour du pays lors des UPSERT TED (absente auparavant), réparation au démarrage des pays retrouvables dans les données TED brutes, démarrage sur « Tous les avis » au lieu de « Ouverts confirmés », diagnostic par pays/source/statut.

**Important** : si le champ `buyer-country` est absent de l’avis TED enregistré, son pays reste UNKNOWN. La correction ne fabrique pas de pays et ne garantit pas qu’un import TED non vérifié fournisse ce champ. La base de chaque version est indépendante, sauf copie volontaire.

Démarrer : `python3 app.py --port 8768`. Diagnostiquer : http://127.0.0.1:8768/api/diagnostics/countries . Réparer manuellement : `python3 app.py --repair-countries`.
