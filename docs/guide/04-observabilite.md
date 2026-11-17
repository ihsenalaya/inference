# 04 - Observabilité : quoi regarder, où, et comment le lire

## 1. Les trois piliers et leur contenu

| Pilier | Outil | Ce qu'il contient | Rétention (config) |
|---|---|---|---|
| **Métriques** | Prometheus (v3.16.0) | séries numériques : vLLM, EPP, LiteLLM, Envoy, istiod, KEDA, Argo CD, DCGM (GPU), Kubernetes | 7 jours, disque managé 8 Gio |
| **Logs** | Loki (3.7.10) alimenté par Alloy | logs de tous les pods, **événements Kubernetes**, access logs JSON de la Gateway | 7 jours, disque 5 Gio |
| **Alertes** | Alertmanager (v0.35.0) | alertes de Prometheus, regroupées, inhibées, envoyées à un webhook (`alert-sink` par défaut) | - |

Grafana (13.3.1) est le point d'entrée : datasources `Prometheus`, `Loki` et `Alertmanager`, 12 dashboards provisionnés depuis Git (`lab.sh ui` -> http://localhost:3000).
Il n'y a **pas de traces** (OpenTelemetry/Tempo non déployés).

**Persistance :** les disques survivent à `lab.sh stop`, **pas** à `lab.sh down` (les mesures sont perdues). Avant une destruction : `./lab.sh snapshot-metrics` (non testé sur cluster) exporte l'historique des règles `lab:*` dans `results/`.

## 2. D'où viennent les métriques (collecte)

Chaque source est déclarée par un `ServiceMonitor` ou un `PodMonitor` (`gitops/observability/config/templates/monitors.yaml`).
Scrape : 15 s pour vLLM, l'EPP, LiteLLM, Envoy ; 30 s par défaut ailleurs.

| Source | Ressource | Port / chemin | Particularité (observé) |
|---|---|---|---|
| vLLM | ServiceMonitor `lab-vllm` | Service `...-workload-svc`, port `http` (8000), `/metrics` | le nom du port a changé entre versions de KServe (`https` en 0.18, `http` en 0.21) |
| EPP llm-d | ServiceMonitor `lab-epp` | port `metrics` (9090) | exige un **jeton** (`bearerTokenFile`) sinon HTTP 401 |
| LiteLLM | ServiceMonitor `lab-litellm` | port `metrics` (9400), chemin **`/metrics/`** avec le `/` final | sans le `/` : redirection 307 ; le port 4000 `/metrics` exige une clé |
| Gateway Istio (Envoy) | PodMonitor `lab-istio-gateway` | port `http-envoy-prom` (15090), `/stats/prometheus` | |
| istiod | ServiceMonitor `lab-istiod` | `http-monitoring` (15014) | |
| GPU (DCGM exporter) | ServiceMonitor du chart GPU Operator | 9400, **intervalle 15 s**, `honorLabels: true` | sans `honorLabels`, `pod` et `namespace` seraient renommés `exported_*` et la jointure GPU/pod vLLM casserait |
| KEDA | ServiceMonitors du chart | 8080 | |
| KServe (contrôleur) | ServiceMonitor `lab-kserve` | HTTPS 8443, jeton | `metricsBindAddress: 0.0.0.0` nécessaire (par défaut 127.0.0.1) |
| cert-manager, Argo CD | ServiceMonitor / PodMonitor | | |
| Kubernetes (kubelet, cAdvisor, kube-state-metrics, node-exporter) | inclus dans kube-prometheus-stack | | scheduler, controller-manager, etcd **désactivés** (plan de contrôle managé AKS) |

Vérification en un coup d'oeil : Prometheus -> *Status -> Targets* (36 cibles `up` mesurées sur Azure) ; le test `lab.sh smoke` échoue si une cible `lab-*` est en erreur.

## 3. Les règles d'enregistrement `lab:*`

Des requêtes lourdes précalculées (`gitops/observability/config/templates/rules.yaml`), pour que les dashboards restent simples et rapides :

| Règle | Signification |
|---|---|
| `lab:ttft_seconds:p50/p95/p99` | TTFT par modèle (`histogram_quantile` sur `vllm:time_to_first_token_seconds`) |
| `lab:itl_seconds:p50/p95` | latence inter-token |
| `lab:e2e_seconds:p95`, `lab:queue_seconds:p95`, `lab:prefill_seconds:p95`, `lab:decode_seconds:p95` | décomposition de la latence |
| `lab:generation_tokens:rate1m`, `lab:prompt_tokens:rate1m`, `lab:requests:rate1m` | débits |
| `lab:requests_running`, `lab:requests_waiting`, `lab:kv_cache_usage:max`, `lab:preemptions:rate5m` | saturation |
| `lab:prefix_cache_hit_ratio` | hits / requêtes du cache de préfixes |
| `lab:tokens_per_second_per_gpu`, `lab:tokens_per_joule`, `lab:cost_per_million_tokens_usd`, `lab:gpu_idle_ratio` | efficacité et coût (prix horaire 0,526 $ codé dans `lab:gpu_hourly_price_usd`) |
| `lab:replica_load_gap`, `lab:epp_decision_seconds:p95`, `lab:litellm_overhead_seconds:p95` | routage et passerelles |
| `lab:vllm_cpu_cores`, `lab:vllm_cpu_throttled_ratio`, `lab:gpu_capacity/allocatable/allocated/used` | CPU et allocation GPU (ajoutés, **non déployés** au moment de la dernière destruction) |

## 4. Les dashboards (dossier Grafana « Lab » + « Imported »)

| Dashboard | À ouvrir quand... | Lecture |
|---|---|---|
| **00 - Cockpit d'optimisation** | toujours, en premier | 6 lignes = 6 questions : utilisateurs servis ? système saturé ? GPU qui travaille ? efficace ? routage correct ? autoscaling qui suit ? |
| **01 - Anatomie d'une requête** | la latence est mauvaise | où va le temps : file, prefill, decode, LiteLLM, Gateway ; heatmaps des distributions |
| **02 - GPU en profondeur** | on soupçonne le GPU ou le CPU | utilisation vs activité du moteur, DRAM, mémoire, puissance, température, XID, PCIe, CPU de vLLM |
| **03 - Capacité et coût** | on parle d'argent | débit max, coût horaire, $ / million de tokens, cold start |
| **04 - Comparaison de runs** | avant/après un changement | les **annotations** de bench (début/fin, profil, scénario, SHA Git) délimitent chaque run |
| **05 - Logs** | une erreur apparaît | Loki : erreurs vLLM, événements Kubernetes, access logs Envoy |
| llm-d (5 dashboards importés) | routage, saturation, cache KV | vue du scheduler llm-d v1.0.0 |
| NVIDIA DCGM Exporter (12239) | santé du GPU | référence NVIDIA |

Chaque panneau porte un titre, une unité et une **description** : ce qu'il mesure et quel levier d'optimisation il éclaire (survolez l'icône « i »).

## 5. Recettes de lecture : du symptôme à la cause

| Vous voyez... | Regardez... | Cause probable (vérifiée sur ce lab) |
|---|---|---|
| TTFT élevé, ITL correct | dashboard 01 (prefill, file) ; `vllm:num_requests_waiting` | prefill lent (prompts longs, attention Triton) ou file d'attente |
| ITL élevé, TTFT correct | dashboard 02 (DRAM, puissance, throttling) | batch trop gros, GPU bridé |
| File non vide, **moteur GPU actif à 80 %+** | dashboard 02 | **saturation de calcul** : c'est ce qui limite le T4 (observé pendant les sweeps) |
| File non vide, GPU peu actif | CPU de vLLM, LiteLLM, Envoy | goulot hors GPU (CPU, passerelle) |
| `vllm:kv_cache_usage_perc` proche de 1, préemptions | dashboard 00 ligne 2 | mémoire KV saturée |
| Hit ratio du cache de préfixes bas | `lab:prefix_cache_hit_ratio`, dashboards llm-d | charge sans préfixe commun, ou routage |
| `litellm` 5xx, connexions réinitialisées | `kubectl -n gateway describe pod`, dashboard 05 | OOMKilled de LiteLLM (observé à 3-4 req/s avant d'élever sa limite) |
| HTTP 500 de la Gateway | logs `istio-proxy` (Loki) : `ext_proc_error_gRPC_error_14` | TLS Envoy -> EPP |
| Dashboards vides | Prometheus > Targets | port ou jeton de scrape, `honorLabels` |
| Un pod vLLM « Running 0/1 » longtemps | `kubectl logs ... -c main` | chargement/compilation (≈ 2,5 min mesurées) |

**Piège d'interprétation** : `DCGM_FI_DEV_GPU_UTIL` est un **rapport cyclique** (« un noyau tournait pendant la période »), pas un taux de travail.
Il peut afficher 100 % avec un GPU très sous-utilisé. Lire plutôt `DCGM_FI_PROF_GR_ENGINE_ACTIVE` (activité du moteur graphique) et `DCGM_FI_PROF_DRAM_ACTIVE` (bande passante mémoire).
Sur le T4, seules ces deux-là (plus PCIe) sont exposées : `SM_ACTIVE`, `SM_OCCUPANCY`, `PIPE_TENSOR_ACTIVE` ne le sont pas avec la configuration actuelle (observé : l'exporteur n'a exposé que `DRAM_ACTIVE`, `GR_ENGINE_ACTIVE`, `PCIE_*` ; cause probable non vérifiée : groupes de compteurs de profilage incompatibles entre eux sur Turing).

## 6. Les métriques à suivre, par couche

Catalogue complet généré depuis le cluster réel : [docs/METRIQUES.md](../METRIQUES.md) (183 métriques). Les essentielles :

**vLLM** (préfixe `vllm:`, 70 familles) - santé du moteur
- `num_requests_running`, `num_requests_waiting` (+ `_by_reason`) : batch et file.
- `kv_cache_usage_perc` (0 à 1), `num_preemptions_total` : mémoire KV.
- `time_to_first_token_seconds`, `inter_token_latency_seconds`, `e2e_request_latency_seconds`, `request_queue_time_seconds`, `request_prefill_time_seconds`, `request_decode_time_seconds` (histogrammes `_bucket/_sum/_count`).
- `prompt_tokens_total`, `generation_tokens_total` : débits. `request_success_total{finished_reason}`.
- `prefix_cache_hits_total` / `prefix_cache_queries_total` : cache de préfixes.
- `estimated_flops_per_gpu_total`, `estimated_read_bytes_per_gpu_total` : « destinés aux calculs de Model Flops Utilization » (texte d'aide de la métrique) : permettent de mesurer à quel point le GPU est exploité.
- `iteration_tokens_total` : tokens par étape moteur (taille effective des batchs).
- `admission_rejections_total` : requêtes refusées par une limite de file (si activée).
- `vllm:corrupted_requests` : **absente** de cette version sans activation ; l'alerte `LabCorruptedRequests` ne peut donc pas se déclencher.

**EPP llm-d** (préfixes `llm_d_epp_`, `inference_extension_`, `inference_objective_`) - routage
- `llm_d_epp_ready_endpoints` : pods prêts du pool (alerte `EPPNoReadyEndpoints`).
- `llm_d_epp_per_endpoint_queue_size`, `llm_d_epp_average_kv_cache_utilization`, `llm_d_epp_std_dev_queue_size` : ce que l'EPP voit de chaque pod ; l'écart-type mesure le déséquilibre.
- `llm_d_epp_request_ttft_seconds`, `llm_d_epp_request_total`, `llm_d_epp_plugin_duration_seconds` : latence vue par l'EPP, coût des plugins.
- `inference_extension_scheduler_e2e_duration_seconds` : durée de décision (règle `lab:epp_decision_seconds:p95`).
  Les deux préfixes (`llm_d_epp_*` et `inference_*`) coexistent dans cette version.

**LiteLLM** (`litellm_`) - passerelle et coûts
- `litellm_proxy_total_requests_metric_total`, `litellm_proxy_failed_requests_metric_total` : taux d'erreur.
- `litellm_overhead_latency_metric` (histogramme) : surcoût de LiteLLM ; `litellm_in_flight_requests`.
- `litellm_spend_metric_total`, `litellm_remaining_team_budget_metric` (labels `team`, `team_alias`) : budgets.

**Envoy / Istio** : `istio_requests_total`, `istio_request_duration_milliseconds` (code de réponse, durée).

**GPU (DCGM)** : `DCGM_FI_DEV_GPU_UTIL`, `_FB_USED`/`_FB_FREE` (MiB), `_POWER_USAGE` (W, plafond 70 W sur T4), `_GPU_TEMP`, `_TOTAL_ENERGY_CONSUMPTION` (mJ), `_CLOCK_THROTTLE_REASONS`, `_XID_ERRORS`, `_ECC_*`, `DCGM_FI_PROF_GR_ENGINE_ACTIVE`, `_DRAM_ACTIVE`, `_PCIE_TX/RX_BYTES`.
Labels utiles (observé) : `pod`, `namespace`, `container`, `modelName`, `gpu`, `Hostname`.

**KEDA / HPA** : `keda_scaler_metrics_value`, `kube_horizontalpodautoscaler_status_desired_replicas`, `kube_deployment_status_replicas_ready`.

**Kubernetes** : `container_cpu_usage_seconds_total`, `container_cpu_cfs_throttled_periods_total`, `kube_pod_container_status_restarts_total`, `kube_pod_container_status_last_terminated_reason` (OOMKilled).

## 7. Les alertes

33 règles d'enregistrement (26 déployées sur Azure + 7 ajoutées ensuite) et 29 alertes (22 `lab-alerts` + 7 `lab-epp-alerts` importées de llm-d), dans `rules.yaml` et `files/epp-rules.yaml`. Chaque alerte porte `severity`, `category` (`slo`, `saturation`, `gpu`, `cost`, `platform`), `component` et une `runbook_url` vers `docs/runbooks/<Alerte>.md` (symptôme, vérifications, leviers).
Les seuils sont **larges par défaut** et à resserrer après mesure (`alertThresholds` dans les scénarios). Inhibition : une cible de scrape absente (`LabScrapeTargetMissing`) masque les alertes SLO du même `component`.
Des alertes sont réellement arrivées au récepteur pendant les tests Azure : `LabTTFTHigh`, `LabInterTokenLatencyHigh`, `LabRequestsWaiting`, `LabGPUIdleCost`, `EPPNoReadyEndpoints` (au démarrage, avant que le modèle soit prêt : normal).

Les **alertes de burn rate** (budget d'erreur SLO) ne sont pas encore écrites : elles font partie de la phase SLO du plan de campagne.

## 8. Les logs (Loki) : requêtes utiles

```logql
{namespace="inference", container="main"} |~ "(?i)error|traceback|oom|cuda"      # erreurs vLLM
{namespace="inference", container="istio-proxy"} | json | response_code >= 500    # erreurs Gateway
{job="loki.source.kubernetes_events"}                                              # événements Kubernetes
{namespace="gateway", container="litellm"} |= "ERROR"                              # erreurs LiteLLM
```
Étiquettes disponibles : `namespace`, `pod`, `container`, `app`, `model`, `job`.

## 9. Annotations de bench

`lab.sh bench` pose dans Grafana une annotation au début et à la fin de chaque run (profil, scénario, SHA Git, cible). Elles apparaissent sur tous les dashboards ; le dashboard 04 sert à comparer deux plages.
Les résultats bruts (JSON `inference-perf`) sont dans `results/<date>-<scénario>-<profil>/` ; `tests/collect_baseline.py` les agrège en tableau ; `tests/check_panels.py` vérifie qu'aucun panneau n'est vide.
