# Atlas v0.8.2

- Retrait de `.history-merged` du package, qui bloquait la fusion historique.
- Fusion idempotente à chaque démarrage; journal détaillé des bases candidates et de leurs nombres d'avis.
- Conservation des avis, favoris et bases sources sans écrasement.
