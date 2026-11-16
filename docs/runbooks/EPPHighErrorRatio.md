# EPPHighErrorRatio

**Symptôme.** Plus de 5 % des requêtes traitées par l'EPP échouent.

## Vérifications

- Logs de l'EPP : `kubectl -n inference logs deploy/<modèle>-kserve-router-scheduler`.

## Leviers d'optimisation

- TLS Gateway -> EPP (DestinationRule).
- Pods vLLM NotReady.
