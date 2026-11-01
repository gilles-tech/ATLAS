# Atlas — audit et plan de redressement (31 octobre 2026)

## Défauts démontrés dans v0.8.6

1. Chaque ZIP stockait ses avis dans un dossier de version : fragmentation et réinitialisations apparentes.
2. Fusion `INSERT OR IGNORE` : un avis incomplet du premier import bloquait l’amélioration depuis les versions suivantes.
3. La liste de sources était principalement déclarative : 82 noms ≠ 82 flux qui alimentent la base.
4. TED retourne une part importante d’avis sans pays exploitable : les 100 000+ lignes ne constituent pas une couverture européenne validée.
5. `ATLAS_TED_PAGES` et les imports par CLI ne garantissent ni exhaustivité ni fonctionnement quotidien.
6. Les tests locaux n’étaient pas des tests de bout en bout avec API live et vrais avis multi-pays.

## Changements réellement livrés dans ce lot

- Base unique `~/AtlasMarches/data/atlas.db`, indépendante des ZIP et des ports HTTP.
- Migration explicite `--merge-history`, avec sauvegarde et réconciliation des champs de meilleure qualité.
- Audit chiffré `--audit` et `/api/audit` (source, pays, échéance, état, exemples TED inconnus).
- Ne plus démarrer une migration massive implicitement à chaque lancement de serveur.
- Les données historiques sont toujours conservées; une preuve géographique absente reste UNKNOWN.

## Barrières de sortie avant de promettre le produit complet

P0 : exécuter le diagnostic sur la vraie base du Mac, mesurer l’inconnu TED et vérifier l’échantillon brut. Tester réellement un appel TED filtré par pays, et contrôler son schéma et son statut d’ouverture.

P1 : ingérer les avis par périodes avec état persistant, contrôles de complétude, reprises et dédoublonnage des notices/lot. Vérifier les dates limites sur les avis officiels.

P2 : connecter de vrais flux publiés par les portails nationaux (Espagne, Italie, Allemagne, etc.), vérifier leurs conditions et leur couverture. Portails authentifiés : workflow de création de comptes, sans contourner les accès.

P3 : tests navigateur Playwright incluant filtres combinés sur avis multi-pays vérifiés, fraîcheur et versions de schémas.

Critère de qualité : chaque source comptée active fournit des avis réels, horodatés, munis d’une URL officielle, et auditables. Aucun compteur catalogué ne doit être confondu avec l’ingestion.
