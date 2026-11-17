# EPPNoReadyEndpoints

**Symptôme.** Le pool n'a aucun endpoint prêt : aucun routage possible.

<!-- mots: cold start -->
> **Mots à connaître**
> - **Cold start** : Délai entre « on demande un GPU / un pod » et « il répond ». Ici : **721 s** pour un nœud GPU, **~3,5 min** pour changer de modèle (observé).
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- Pods vLLM prêts ? `kubectl -n inference get pods`

## Leviers d'optimisation

- Cold start en cours ; patienter ou vérifier le chargement du modèle.
