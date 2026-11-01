# Atlas v0.8.6 – Recherche réparée et multilingue (premier niveau)

- Recherche SQL AND entre mots, OR pour chaque groupe de traductions contrôlées. Accents et casse normalisés.
- Recherche dans les titres, descriptions, acheteurs et CPV (évite de rechercher aveuglément dans les JSON bruts qui produisent des faux positifs).
- Interrupteur « Recherche multilingue », activé par défaut, et retour API `search_info` pour la transparence.
- Traductions métiers intégrées pour une vingtaine de concepts FR/EN/DE/ES/IT/NL/PT/PL ; **ce n'est pas une traduction automatique universelle**. Les termes non connus sont recherchés littéralement, donc aucune garantie de couverture exhaustive des 24 langues.
- La base SQLite locale n'est pas livrée dans le ZIP. La migration de l'historique préexistant reste disponible.

## Installation

`cd ~/Downloads && unzip -o atlas-marches-mvp-v0.8.6-search.zip && cd atlas-marches-mvp-v0.8.6 && python3 app.py --merge-history && python3 app.py --port 8778`

Ne pas ouvrir plusieurs versions d'Atlas en écriture sur la même base. La recherche est indexée sur les avis effectivement importés uniquement.
