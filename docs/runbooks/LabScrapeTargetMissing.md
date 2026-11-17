# LabScrapeTargetMissing

**Symptôme.** Une cible de scrape (vLLM, DCGM, LiteLLM) est absente.

<!-- mots: cold start, dcgm, gitops -->
> **Mots à connaître**
> - **Cold start** : Délai entre « on demande un GPU / un pod » et « il répond ». Ici : **721 s** pour un nœud GPU, **~3,5 min** pour changer de modèle (observé).
> - **DCGM** : Outil NVIDIA qui mesure le GPU ; `dcgm-exporter` publie ces mesures pour Prometheus.
> - **GitOps** : L'état voulu du cluster est écrit dans Git ; Argo CD le fait appliquer. On ne modifie pas le cluster à la main.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- Prometheus > Status > Targets ; ServiceMonitors de `gitops/observability/config`.

## Leviers d'optimisation

- Port du Service workload (`http` depuis KServe 0.21).
- `honorLabels` du ServiceMonitor DCGM.
- Pods NotReady (cold start en cours ?).
