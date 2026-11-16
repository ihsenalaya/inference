# LabScrapeTargetMissing

**Symptôme.** Une cible de scrape (vLLM, DCGM, LiteLLM) est absente.

## Vérifications

- Prometheus > Status > Targets ; ServiceMonitors de `gitops/observability/config`.

## Leviers d'optimisation

- Port du Service workload (`http` depuis KServe 0.21).
- `honorLabels` du ServiceMonitor DCGM.
- Pods NotReady (cold start en cours ?).
