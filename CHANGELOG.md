# v0.5.1 — Correctif pays/recherche TED

- Les pays TED ne sont plus remplacés par le faux code `EU`. Les valeurs non identifiables sont `UNKNOWN`.
- Nouvelle API `/api/countries` avec nombres effectivement indexés, utilisée par le filtre déroulant.
- `UE` filtre les 27 codes nationaux et non la seule chaîne `EU`.
- La recherche inclut aussi les données brutes TED quand titre/description sont peu renseignés.
- **Important : les anciens avis TED déjà indexés `EU` doivent être réimportés** ; les vrais pays n'étaient pas enregistrés par l'ancien connecteur.
- Pas de certification de bout en bout TED sans import réel de test.
