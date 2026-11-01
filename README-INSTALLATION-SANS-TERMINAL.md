# Atlas Marchés — Installation Mac sans Terminal

## Pour l'utilisateur final (après compilation et signature du DMG)

1. Télécharger **AtlasMarches-macOS.dmg** depuis la page de distribution.
2. Double-cliquer sur le DMG et déposer **AtlasMarches.app** dans **Applications**.
3. Ouvrir Atlas Marchés depuis Applications.
4. Lors du premier lancement, accepter (ou refuser) la proposition de synchronisation quotidienne BOAMP/TED. Une acceptation crée automatiquement un LaunchAgent **pour cet utilisateur**, sans Terminal ni droits administrateur.

Les avis et favoris restent dans `~/AtlasMarches/data/atlas.db`, hors de l'app. Installer une mise à jour ne doit jamais écraser cette base. La collecte ne peut pas s'exécuter Mac éteint et dépend de la disponibilité réseau et de la session utilisateur.

## Pour le propriétaire du produit (construction / distribution, une seule fois)

Le ZIP ci-joint est le **code du constructeur**, **pas encore un installateur DMG précompilé**. Le `.app` doit être compilé sur macOS (via le workflow GitHub Actions inclus ou `build_macos.command`). L'utilisateur final ne reçoit **que le DMG** et n'a pas besoin de Python ni de Terminal.

Avant distribution grand public : signature Developer ID, notarisation Apple, tests sur Mac vierge, validation des permissions réseau et des mises à jour. Sans signature/notarisation, Gatekeeper peut bloquer l'ouverture.

## Vérification avant publication

- Construire le DMG via GitHub Actions sur un runner macOS, puis tester manuellement sur un Mac vierge.
- Ouvrir l'application depuis `/Applications` et vérifier que la fenêtre charge les résultats.
- Valider le consentement de synchronisation et vérifier la présence du LaunchAgent.
- Vérifier que les données préexistantes dans `~/AtlasMarches/data/atlas.db` subsistent après mise à jour.
- Tester fermeture/réouverture, gestion des ports, recherche et filtres, journal des synchronisations.
- Tester l'app signée/notarisée séparément avant distribution publique.
