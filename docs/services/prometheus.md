# Prometheus (kube-prometheus-stack)

**En une phrase.** Prometheus est le relevé de compteurs du cluster : toutes les 15 à 30 secondes il va lire les chiffres de chaque composant et les garde 7 jours pour qu'on puisse les tracer et déclencher des alertes.

<!-- mots: prometheus, métrique, scrape, promql, recording rule, servicemonitor -->
> **Mots à connaître**
> - **Prometheus / Alertmanager** : Stocke les métriques / envoie les alertes.
> - **Métrique** : Un nombre mesuré dans le temps (ex. `vllm:num_requests_waiting`). *Counter* = ne fait que monter ; *gauge* = monte et descend.
> - **Scrape / cible** : Prometheus interroge périodiquement chaque programme exposant `/metrics`.
> - **PromQL** : Langage de requête de Prometheus.
> - **Recording rule** : Requête PromQL précalculée et enregistrée comme nouvelle métrique (nom en `lab:` ou `slo:`).
> - **ServiceMonitor / PrometheusRule** : Objets qui déclarent à Prometheus quoi scruter / quelles règles et alertes appliquer.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Rôle
Collecte, stocke et interroge les **métriques**. Déployé par le chart `kube-prometheus-stack` 93.3.0 (nom court `kps`), qui apporte aussi l'opérateur, kube-state-metrics, node-exporter, Alertmanager et Grafana. Namespace `monitoring`.

## Composants (observé)
| Composant | Version | Rôle |
|---|---|---|
| `prometheus-kps-prometheus` (StatefulSet) | v3.16.0 | base de séries temporelles, évaluation des règles |
| `kps-operator` (Prometheus Operator) | v0.95.2 | transforme `ServiceMonitor`, `PodMonitor`, `PrometheusRule` en configuration |
| `kube-state-metrics` | v2.20.0 | métriques sur l'**état des objets** Kubernetes (pods, déploiements, HPA...) |
| `node-exporter` (DaemonSet) | v1.12.1 | métriques de chaque nœud (tolère le taint GPU) |

## Place dans l'architecture
Il **scrape** toutes les cibles listées dans le [guide observabilité §2](../guide/04-observabilite.md) et alimente Grafana, Alertmanager, et **KEDA** (qui lit `vllm:num_requests_waiting` chez lui). Il tourne sur le pool système.

## Relations
- **Découvre** les cibles par l'API Kubernetes (ServiceAccount `kps-prometheus`, ClusterRole : nodes, services, endpoints, pods, endpointslices ; `nonResourceURLs /metrics`).
- **Alimente** : Grafana (datasource `prometheus`), Alertmanager (alertes), KEDA (requête de trigger), `inference-perf` (métriques serveur pendant un bench).

## Configuration retenue (config : `gitops/observability/kube-prometheus-stack`)
- `serviceMonitorSelectorNilUsesHelmValues: false` (idem pour pod monitors, règles, probes) : découvre les objets de **tous** les namespaces.
- Rétention **7 jours**, `scrapeInterval` et `evaluationInterval` 30 s (15 s pour vLLM/EPP/LiteLLM/Envoy/DCGM via leurs monitors). PVC **8 Gio** `managed-csi` sur Azure.
- Ressources : requests 200 m / 768 Mi, limite mémoire 1,5 Gio.
- Plan de contrôle managé : scrapes `kube-scheduler`, `kube-controller-manager`, `etcd`, `kube-proxy` **désactivés** (inaccessibles sur AKS, fausses alertes).
- Règles : `lab-recording` (33 enregistrements), `lab-slo` (59 enregistrements + 2 alertes de burn rate), `lab-alerts` (19 alertes), `lab-epp-alerts` (7) + les règles par défaut du chart. Les 4 groupes `lab.slo*` ont été évalués sans erreur sur le cluster du 17/11.

## Authentification
Scrapes anonymes en HTTP, sauf EPP et KServe (jeton `bearerTokenFile` du ServiceAccount). Prometheus lui-même n'a pas d'authentification (accès par port-forward).

## Données traitées
Des **séries numériques** (étiquettes + valeurs), jamais de contenu de requête. Attention aux étiquettes à forte cardinalité : LiteLLM expose `hashed_api_key`, `model_id`...

## Contribution à l'inférence
Fournit les signaux pour décider : file d'attente, cache KV, latences, utilisation GPU. Sert aussi de **bus** : l'autoscaling KEDA et l'EPP (côté métriques de pods) en dépendent indirectement. Si Prometheus tombe, KEDA perd son signal (comportement à tester).

## Métriques à suivre sur Prometheus lui-même
`up` (cibles), `prometheus_tsdb_head_series`, `prometheus_rule_evaluation_failures_total`, `scrape_duration_seconds`. 36 cibles `up` observées sur Azure ; alerte `LabScrapeTargetMissing`.

## Pannes et diagnostic
| Symptôme | Cause |
|---|---|
| cible `down` 401 | jeton manquant (EPP, KServe) |
| cible `down` 307/401 sur LiteLLM | mauvais port/chemin (utiliser `:9400/metrics/`) |
| `ComparisonError ... Alertmanager` dans Argo CD | CRDs pas encore installées (réessais) |
| séries DCGM sans `pod` | `honorLabels` absent |
| données perdues après `down` | disque supprimé ; exporter avant avec `lab.sh snapshot-metrics` |
