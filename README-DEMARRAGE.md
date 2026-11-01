# Atlas Recovery v1 — instructions Mac

Décompresser le ZIP dans Téléchargements, puis :

```bash
cd ~/Downloads/atlas-marches-recovery-v1
python3 app.py --merge-history  # lance une fois la fusion des versions précédentes
python3 app.py --audit          # imprime les véritables chiffres
python3 app.py --port 8780     # démarre le serveur
```

Ouvrir http://127.0.0.1:8780/index.html et le diagnostic http://127.0.0.1:8780/api/audit.

**Les 107 100 avis ne sont pas inclus dans le ZIP : ils résident sur votre Mac.** La migration ne pourra récupérer que les bases réellement présentes dans ~/Downloads/atlas-marches-mvp*/atlas.db. La sauvegarde se trouve dans ~/AtlasMarches/data/. Aucune suppression automatique des originaux.

Ne pas publier le serveur : application locale sans authentification. TED et BOAMP sont les seuls adaptateurs spécifiques codés; aucune prétention de couverture exhaustive des 82 sources.
