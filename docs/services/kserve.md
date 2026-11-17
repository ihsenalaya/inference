# KServe (`LLMInferenceService`)

## Rôle
Le **plan de contrôle du serving**. On écrit un objet déclaratif `LLMInferenceService` (modèle, image, arguments, ressources) ; le contrôleur `llmisvc-controller-manager` en déduit et maintient tous les objets nécessaires.
Version **v0.21.0** (25/09/2026), API `serving.kserve.io/v1alpha2` (la `v1alpha1` reste servie). Seule la partie « LLM » de KServe est installée (charts `kserve-llmisvc-crd`, `kserve-llmisvc-resources`, `kserve-runtime-configs`).

## Place dans l'architecture
Namespace `kserve` : un seul workload (`llmisvc-controller-manager`, 50 m CPU / 128 Mi, limite 512 Mi). Il agit sur le namespace `inference`.

## Relations
- **Lit** : les `LLMInferenceService` (créés par Argo CD depuis notre chart `gitops/serving/chart`) et les **presets** `LLMInferenceServiceConfig` (namespace `kserve`) qu'il fusionne avec la spec.
- **Crée** : Deployment vLLM + Service, Deployment EPP + Service + RBAC, `InferencePool`, `HTTPRoute`, `ScaledObject` KEDA si `spec.scaling.keda` (voir [architecture §3](../guide/02-architecture.md)).
- **S'appuie sur** : cert-manager (certificat du webhook), Gateway API + GIE (objets), Istio (implémentation de la Gateway), KEDA (autoscaling), LeaderWorkerSet (dépendance, inutilisée).

## Configuration retenue (config : `gitops/platform/kserve-*`, `gitops/serving/chart`)
- Presets activés : `kserve.llmisvcConfigs.enabled: true` (runtime-configs). Sans cela : `PresetsCombined=False ... ConfigNotFound`.
- Chart `kserve-llmisvc-resources` : `createGIECRDs: false` (installées en vague 0), `metricsBindAddress: 0.0.0.0` (scrape Prometheus), ressources du contrôleur réduites.
- **`kserve.storage.resources`** : limite mémoire du `storage-initializer` relevée à **6 Gio** : à 1 Gio il était tué par OOM en téléchargeant le 7B (observé, code 137).
- **Pas d'Envoy Gateway ni d'Envoy AI Gateway** : une `Gateway` de classe `istio` référencée par `spec.router.gateway.refs` suffit (vérifié).
- **Surcharge du conteneur `main`** dans chaque `LLMInferenceService` (chart de serving) :
  - image **`vllm/vllm-openai@sha256:befccf0e…`** (v0.32.0) au lieu de l'image du preset `ghcr.io/llm-d/llm-d-cuda:v0.9.0`, qui est compilée **sans sm_75** (T4) : inutilisable ;
  - arguments `--dtype float16 --max-model-len 4096 --gpu-memory-utilization 0.90 --enable-prefix-caching` ;
  - `runAsUser: 1000` (l'image officielle tourne en root, le preset impose `runAsNonRoot`) ;
  - `startupProbe.failureThreshold: 120` (jusqu'à 20 minutes de démarrage) ;
  - requests 2 500 m CPU / 18 Gio, limites 22 Gio et 1 GPU ; `nodeSelector workload=inference` + toleration du taint GPU.
- **`rolloutStrategy: {maxSurge: 0, maxUnavailable: 1}`** : avec 1 GPU par pod et 2 GPU de quota, pas de pod de remplacement possible en parallèle : sans cela le rolling update reste bloqué en `Pending`.
- Le **TLS interne de KServe est inactif** (probes en HTTP, vLLM sert en HTTP) : aucun certificat n'est monté en usage.

## Authentification
- ServiceAccount `llmisvc-controller-manager`, `ClusterRole kserve-llmisvc-manager-role`, élection de leader par `Role` (leases).
- Son webhook est servi en HTTPS (certificat cert-manager, secret `llmisvc-webhook-server-cert`). Deux `ValidatingWebhookConfiguration` (`llminferenceservice`, `llminferenceserviceconfig`) et une `Mutating`.
- Aucune authentification des **clients** d'inférence : c'est le rôle de LiteLLM.

## Données traitées
Des **objets de configuration** uniquement : il ne voit ni prompts ni tokens.

## Contribution à l'inférence
Il fait exister toute la chaîne de serving à partir d'un fichier de scénario (`gitops/scenarios/<nom>.yaml`) et l'adapte (réplicas, `scaling.keda`). Il impose aussi des **conventions** que le reste du lab suit : chemin public `/<namespace>/<nom>/v1/...` (ici `/inference/<nom>/...`), nom de port `http`, labels `kserve.io/component`, nom de l'EPP `<nom>-epp-service`.

## Métriques à suivre
Contrôleur (`controller_runtime_*`, via `lab-kserve`) ; surtout l'**état des objets** : `kubectl -n inference get llminferenceservice` (colonnes READY/REASON) et `.status.conditions` (`PresetsCombined`, `RouterReady`, `WorkloadsReady`).

## Pannes et diagnostic (observé)
| Symptôme | Cause / correction |
|---|---|
| `Ready=False ConfigNotFound ... kserve-config-llm-scheduler` | presets non activés (`llmisvcConfigs.enabled`) |
| `MinimumReplicasUnavailable` longtemps | pod en `Pending` (GPU non annoncé / driver en cours) ou en démarrage (jusqu'à ~20 min à froid) |
| `CreateContainerConfigError ... runAsNonRoot and image will run as root` | `runAsUser: 1000` manquant |
| `Init:CrashLoopBackOff`, code 137 | `storage-initializer` OOM (limite mémoire trop basse) |
| Rolling update coincé (`ProgressDeadlineExceeded`) | pas de surge possible : `rolloutStrategy` |
| Changement de limites sans effet | KServe lit sa config au moment de réconcilier : relancer le contrôleur (`rollout restart`) |
