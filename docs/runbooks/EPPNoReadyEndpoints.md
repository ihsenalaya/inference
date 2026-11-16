# EPPNoReadyEndpoints

**Symptôme.** Le pool n'a aucun endpoint prêt : aucun routage possible.

## Vérifications

- Pods vLLM prêts ? `kubectl -n inference get pods`

## Leviers d'optimisation

- Cold start en cours ; patienter ou vérifier le chargement du modèle.
