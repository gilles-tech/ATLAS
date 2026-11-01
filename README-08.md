# Atlas v0.8 — Poste de recherche

Lancer `python3 app.py --port 8772`, puis ouvrir http://127.0.0.1:8772/index.html.

Filtres serveur SQL : mots-clés, pays, source, statut, nature, acheteur/groupe, région, CPV, intervalles de dates et montants, tri. Facettes indiquant la disponibilité réelle des valeurs. Recherches nommées conservées dans le navigateur et lien partageable.

**Limite de couverture** : 82 sources cataloguées, BOAMP/TED codés, moteur RSS/Atom activable. Les autres profils institutionnels, portails avec authentification, sites sans API ni flux vérifié ne sont pas intégrés. Ne pas compter ces sources comme actives. Aucune collecte en ligne n'a été validée dans ce build.

Les recherches enregistrées sont locales au navigateur, et non partagées entre appareils.
