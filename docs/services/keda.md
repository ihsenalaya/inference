# KEDA (autoscaling piloté par métriques)

## Rôle
Ajuste le **nombre de réplicas** d'un déploiement à partir d'un signal externe (ici une requête Prometheus). Version **2.21.1**. Sous le capot, KEDA fabrique et alimente un **HPA** Kubernetes.

## Place dans l'architecture
Namespace `keda`, 3 workloads : `keda-operator` (réconcilie les `ScaledObject`), `keda-operator-metrics-apiserver` (fournit les métriques externes au HPA), `keda-admission-webhooks`.
Il n'est pas configuré par nous directement : c'est **KServe** qui crée le `ScaledObject` quand un scénario déclare `spec.scaling.keda`.

## Relations
`LLMInferenceService.spec.scaling` -> KServe crée `ScaledObject <nom>-kserve-keda` -> KEDA crée le HPA `keda-hpa-<nom>-kserve-keda` -> HPA modifie `replicas` du Deployment vLLM. KEDA **interroge Prometheus** (`http://kps-prometheus.monitoring.svc:9090`).

## Configuration retenue (scénario `baseline-7b-keda`)
- min 1, max 2 réplicas (quota : 2 GPU) ; **pas de scale-to-zero** (un nouveau réplica met plusieurs minutes).
- Trigger `prometheus` : `sum(vllm:num_requests_waiting{...}) / count(vllm:num_requests_waiting{...})`, seuil **2** (requêtes en attente par réplica), `pollingInterval: 15`, `cooldownPeriod: 300`.
- Métriques de KEDA exposées à Prometheus (ServiceMonitors du chart).

## Authentification
Aucune vers Prometheus (URL interne). ServiceAccounts propres (`keda-operator`, `keda-metrics-server`), ClusterRoles du chart.

## Données traitées
Une valeur numérique (la file d'attente moyenne). Pas de contenu de requête.

## Contribution à l'inférence
Ajoute de la capacité quand la file grossit. **Mesuré** (burst 4 req/s sur le 7B, 2 nœuds T4) : décision de scale-out ~1-2 min après le début du pic ; **2e pod prêt 6 min 51 s après la décision** (dont 3 min 31 de pull d'image sur un nœud neuf) ; premier token servi par le nouveau réplica 10 s après ; retour à 1 réplica ~5 min après la fin du pic (cooldown). Le point faible est donc le **démarrage à froid**, pas la décision.

## Métriques à suivre
`keda_scaler_metrics_value` (valeur du trigger), `keda_scaled_object_errors_total`, `kube_horizontalpodautoscaler_status_desired_replicas`, `kube_deployment_status_replicas_ready`. Alerte `LabKedaAtMaxWithQueue` : au maximum avec une file non vide.

## Pannes et diagnostic
- Si Prometheus est indisponible, le HPA ne reçoit plus de métrique : le comportement exact (champ `fallback` de KEDA) est à tester (game day).
- Une requête trigger qui ne retourne aucune série (aucun pod prêt) laisse le HPA sans valeur (`<unknown>/2`, observé au démarrage).
- Avec 1 seul nœud GPU, le 2e réplica restera `Pending` : `gpuNodes` plafonne les réplicas fixes, pas le `maxReplicas` KEDA.
