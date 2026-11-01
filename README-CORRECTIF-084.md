# Atlas v0.8.4 — diagnostic et réparation géographique TED

Cette version préserve les bases locales des versions antérieures via la migration Atlas existante. Aucune base pré-remplie n’est fournie.

## Réparation sans réseau
`python3 app.py --repair-countries`

## Enrichissement à partir des XML officiels TED
`python3 app.py --enrich-ted-countries --enrich-limit 100`

Ce traitement est volontairement progressif : seuls les avis TED dont le pays est inconnu sont interrogés, et un pays est enregistré uniquement lorsque le XML contient un pays d'acheteur non ambigu. Tous les avis sans pays restent consultables dans Tous les pays. Des résultats non classés ne prouvent pas que le marché ne concerne aucun pays.

**Important :** les avis TED déjà importés avec un payload minimal ne peuvent pas tous être réparés localement. Le téléchargement XML peut être long, répondre 429 ou ne pas contenir l'information exploitable. La commande fonctionne par lots, sans supprimer les avis et sans inventer une classification.

Les filtres géographiques continuent d'exclure les avis dont le pays reste inconnu. Le diagnostic `/api/diagnostics/countries` permet d'en mesurer le nombre.

## Démarrage
`python3 app.py --port 8776` puis http://127.0.0.1:8776/index.html
