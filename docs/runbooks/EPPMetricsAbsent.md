# EPPMetricsAbsent

**Symptôme.** Aucune métrique EPP n'est collectée.

## Vérifications

- ServiceMonitor `lab-epp`, jeton du ServiceAccount Prometheus.

## Leviers d'optimisation

- Authentification du /metrics de l'EPP (bearerTokenFile).
