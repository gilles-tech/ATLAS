# Atlas Marchés — création du DMG macOS

## Livraison à l'utilisateur final

Télécharger un DMG correspondant à son Mac (Apple Silicon ou Intel), double-cliquer sur le DMG, glisser AtlasMarches.app vers Applications, puis ouvrir Atlas depuis Applications. Aucun Python ou Terminal n'est nécessaire pour l'utilisateur final.

La base existante est conservée dans `~/AtlasMarches/data/atlas.db`. Les installateurs n'embarquent pas de base pré-remplie. L'application propose, au premier démarrage, l'activation d'une mise à jour quotidienne à 6 h (Mac en session). Les données ne sont pas automatiquement récupérées d'un Mac vers un autre.

## Compiler le DMG sans Terminal sur le Mac utilisateur

Pour le responsable de publication :
1. Importer les fichiers de ce dossier dans un dépôt GitHub privé (la racine du dépôt doit contenir `app.py`, `desktop.py`, `static/`, `packaging/` et `.github/`).
2. Aller dans GitHub > Actions > **Atlas Marches — macOS DMG** > **Run workflow**.
3. À la fin des deux jobs, télécharger les artefacts `AtlasMarches-macOS-AppleSilicon-unsigned` et `AtlasMarches-macOS-Intel-unsigned`.
4. Tester les DMG sur des Macs propres. Les artefacts sont des builds **non signés** ; ils peuvent être bloqués par Gatekeeper. Pour une distribution au public sans avertissement, une signature Developer ID et une notarisation Apple sont requises. Les étapes de signature/notarisation ne sont pas mises en œuvre dans cette version.

Le workflow est à lancer via GitHub Actions sur un véritable runner macOS. PyInstaller ne permet pas de compiler un binaire macOS natif depuis Linux. Les jobs doivent disposer d'une connexion réseau pour installer les dépendances. Le programme `launchd` quotidien nécessite une session macOS ouverte ; il ne garantit pas une collecte si le Mac est éteint.

## Compatibilité et limites

- Apple Silicon ARM64 : runner `macos-15`.
- Intel x86_64 : runner `macos-15-intel` (disponibilité selon le compte GitHub).
- Aucune donnée existante n'est écrasée à l'installation ; conserver une sauvegarde de `atlas.db`.
- Source de données active dans ce code : BOAMP et TED. Les autres sources figurent dans un catalogue et ne doivent pas être annoncées comme collectées.
- Le build packaging ne vaut pas un test d'ingestion réseau ni une signature du DMG.
