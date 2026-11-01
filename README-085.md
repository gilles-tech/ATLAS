# Atlas v0.8.5 — sources et comptes

Conserve l’ensemble de la v0.8.4 (réparation TED, migration de bases et moteur de recherche).

## Nouveautés
- Registre des 82 sources à `/api/access-registry` : liens officiels, état réel, nombre d’avis, liens d’inscription vérifiés pour TED, EU Funding & Tenders, BERD ECEPP, UNGM.
- Panneau « Sources & comptes fournisseurs » accessible depuis chaque page, recherche par nom et pays.
- Aucune création de compte automatique, aucune donnée d'identification enregistrée.

## Limites explicites
Les 80 sources cataloguées sans adaptateur actif **ne sont pas intégrées en ingestion**. Les liens d'inscription non vérifiés ne sont pas inventés. Certains portails n'ont pas d'API publique ou nécessitent une validation du compte fournisseur. Le simple registre ne résout pas cette limitation.

## Lancer
`python3 app.py --merge-history` puis `python3 app.py --port 8777`.

## Réparer les avis TED existants
`python3 app.py --repair-countries`
`python3 app.py --enrich-ted-countries --enrich-limit 250`

Ne jamais écraser les anciennes bases avant de les avoir sauvegardées.
