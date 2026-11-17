# EPPMetricsAbsent

**Symptôme.** Aucune métrique EPP n'est collectée.

<!-- mots: epp -->
> **Mots à connaître**
> - **llm-d / EPP** : *Endpoint Picker* : choisit le pod vLLM le mieux placé (peu chargé, cache de préfixes) pour chaque requête.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- ServiceMonitor `lab-epp`, jeton du ServiceAccount Prometheus.

## Leviers d'optimisation

- Authentification du /metrics de l'EPP (bearerTokenFile).
