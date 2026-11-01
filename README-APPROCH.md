# APProch — Source de projets d’achats prévisionnels

**Source** : https://projets-achats.marches-publics.gouv.fr/  
**Données ouvertes** : https://www.data.gouv.fr/datasets/projets-dachats-publics  
**Export CSV officiel** : `https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/projets-dachats-publics/exports/csv?lang=fr&timezone=Europe%2FParis&use_labels=true&delimiter=%3B`

## Importation automatique

La synchronisation `sync_daily.py` appelle maintenant `APPROCH`, en plus de BOAMP, TED et EU FT. L'import récupère le CSV public et actualise les fiches avec upsert. Le CSV peut changer de colonnes ; une absence de champs obligatoires produit une erreur explicite au lieu de faux résultats.

## Import du fichier personnel XLSX/CSV

`python3 app.py --import-approch /chemin/approch_export_projets.xlsx`

Testé sur l'export du 1er novembre 2026 (100 lignes, 94 projets distincts après dédoublonnage). Le fichier n'est pas inclus dans le ZIP : conserver l'original localement.

## Classification

Les projets sont enregistrés avec `source=APPROCH`, `stage=future`, `kind=FUTURE_PROJECT`. Le champ « Statut = Ouvert » et la « Date cible de remise des offres » ne certifient pas une procédure de marché actuellement ouverte. Les dates cibles demeurent dans `raw`, jamais dans le champ `deadline` réservé aux échéances de consultation confirmées.

Pour voir les projets dans Atlas : sélectionner source APProch et statut **Projets prévisionnels**, ou statut Tous. Les projets n'apparaissent pas dans « Ouverts confirmés ».

## Limitations

Les projets d'achat sont volontairement publiés par les acheteurs, donc non exhaustifs. L'export officiel et le fichier manuel peuvent différer selon leurs dates de création. Certains projets ne présentent pas de lien de consultation (projet en amont de l'appel d'offres). L'accès à l'API export dépend du réseau ; l'ingestion distante devra être testée sur Mac.
