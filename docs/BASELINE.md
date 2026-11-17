# Baseline du lab d'inférence (AKS, 1 x T4)

Mesures du 16-17/11/2026 sur le cluster déployé par `./lab.sh up` (région eastus, abonnement personnel).
Rien n'a été optimisé : ce document décrit l'état initial et liste des pistes, classées par gain potentiel (section 9).

## 1. Versions exactes déployées

| Composant | Version |
|---|---|
| AKS | 1.34 (tier Free), Ubuntu 22.04.5, noyau 5.15.0-1126-azure, pas de mise à jour automatique |
| Pools | système `Standard_D4as_v7` (4 vCPU, 16 Gio), GPU `Standard_NC4as_T4_v3` (1 T4 16 Go, 4 vCPU, 28 Gio) |
| NVIDIA GPU Operator | v26.7.2, driver **580.95.05** (modules propriétaires), CUDA 13.0, DCGM exporter 4.6.1 |
| KServe `LLMInferenceService` | v0.21.0 (`serving.kserve.io/v1alpha2`), llm-d router (EPP) v0.10.0 |
| vLLM | **v0.32.0** (`vllm/vllm-openai@sha256:befccf0e...`), PyTorch/CUDA 13.0.2 |
| Istio | 1.30.8 (istiod seul, Gateway API v1.5.1, GIE v1.5.0) |
| LiteLLM | v1.109.1 (image par digest), PostgreSQL 16 |
| KEDA | 2.21.1 ; LeaderWorkerSet 0.8.0 ; cert-manager v1.17.4 |
| kube-prometheus-stack | 93.3.0 ; Loki 3.7.10 (chart 21.2.3) ; Alloy v1.22.0 |
| Argo CD | v3.6.1 (chart 10.18.0) ; inference-perf v0.7.0 |
| Terraform | azurerm 5.14.0, helm 3.3.0, kubernetes 3.5.0 |

Liste complète et sources : `gitops/root/versions.yaml` ; écarts avec le prompt : `docs/DECISIONS.md`.

## 2. Backend d'attention de vLLM sur T4

Relevé dans les logs du pod (vLLM v0.32.0) :

```
Using TRITON_ATTN attention backend out of potential backends: ['TRITON_ATTN', 'FLEX_ATTENTION'].
Cannot use FA version 2 is not supported due to FA2 is only supported on devices with compute capability >= 8
Using MarlinLinearKernel for AutoAWQMarlinLinearMethod
```

- Le T4 (sm_75) n'a que `TRITON_ATTN` ou `FLEX_ATTENTION` : FlashAttention exige sm_80+, FlashInfer est bridé à sm_80+.
- Depuis Triton 3.3 ces noyaux n'utilisent plus les tensor cores sur Turing (issue vllm #60821).
- La PR #55380 (« Restore flashinfer support for SM75 ») est **encore ouverte** (non fusionnée) et absente de v0.32.0 comme de v0.33.0rc3 :
  il n'existe pas de release qui la contienne. La PR #61015 (avertissement) est aussi ouverte.
- `--max-model-len 4096` est conservé pour la base. L'image `llm-d-cuda:v0.9.0` fournie par KServe est compilée sans sm_75 : non utilisable (D-03).
- **Expérience A/B décrite (non exécutée)** : même scénario avec (A) `vllm/vllm-openai:v0.32.0` (base) et (B) une image construite depuis la branche de la PR #55380
  (ou une version ultérieure qui l'intègre), profil `long-prompt` puis `sweep`. Critère : TTFT p50 du profil `long-prompt` (base : **102 s**, collapse) et
  débit de prefill. Un fork communautaire n'est pas utilisé sans accord (règle 10).

## 3. Cold start (déploiement depuis zéro)

Déploiement **entièrement automatique** depuis un groupe de ressources vide (`./lab.sh up`, aucune action manuelle),
mesuré sur la seconde installation (après `down`), 1 nœud T4, modèle `qwen-7b-awq` :

| Phase | Durée |
|---|---|
| `terraform apply` (groupe de ressources, AKS, pool GPU, Argo CD, secrets, application racine) | 575 s (AKS 5 min 00, pool GPU 1 min 54) |
| Convergence Argo CD des 19 applications (jusqu'à tout Synced/Healthy) | ~10 min 30 |
| Pods prêts (driver, modèle, vLLM) | à 03:51:41 |
| **Total `lab.sh up` jusqu'à `smoke` 9/9 vert** | **28 min 46 s** |

Détail du cold start GPU (nœud GPU créé -> vLLM prêt), lu dans les objets Kubernetes (`tests/coldstart.py`) :

```
Étape                                              Durée
nœud GPU créé -> driver NVIDIA démarré (attente Argo CD + GPU Operator)    590 s
installation du driver (compilation des modules noyau)                  191 s
nœud GPU créé -> GPU annoncé (nvidia.com/gpu)                           804 s
pod vLLM planifié -> modèle téléchargé (storage-initializer)             41 s
modèle téléchargé -> conteneur vLLM démarré (pull image ~9 Go)          215 s
conteneur démarré -> Ready (chargement + compilation + graphes CUDA)    154 s
nœud GPU créé -> vLLM Ready (total)                                    1228 s

vLLM : poids 21.69 s ; modèle 5.29 GiB ; torch.compile 19.79 s ; init moteur 72.75 s ; cache KV 130,512 tokens
backend d'attention : TRITON_ATTN ; noyau linéaire : MarlinLinearKernel
```

Lecture :
- Le driver n'est compilé qu'après **~10 min** d'attente : le GPU Operator est en vague 3 d'Argo CD, derrière cert-manager et kube-prometheus-stack
  (piste : le passer en vague 1 pour compiler le driver en parallèle).
- La compilation du driver prend ~3 min 11 (modules propriétaires ; les modules ouverts ne compilent pas sur ce noyau, D-18).
- L'image vLLM (~9 Go) est tirée **après** le téléchargement du modèle (3 min 35), car l'init container précède le conteneur principal
  (piste : pré-tirer l'image par un DaemonSet dès que le nœud est prêt).
- vLLM : poids 21,7 s, torch.compile 19,8 s, graphes CUDA ~28 s, initialisation du moteur 72,8 s ; cache KV 130 512 tokens.
- Redémarrage après `lab.sh stop` : `az aks start` 5 min 13, puis ~11 min de pods (les nœuds sont recréés : nouveau driver, nouvelle image).
- Nœud supplémentaire (KEDA, 2e T4) : nœud prêt en 1 min 49, driver ~3 min, pod Ready ~7 min après la décision (voir section 7).

## 4. Mémoire GPU par modèle

| Modèle | Mémoire GPU utilisée | Détail |
|---|---|---|
| `Qwen2.5-7B-Instruct-AWQ` (4 bits, Marlin) | **14 447 MiB** / 16 384 | poids 5,29 Gio, cache KV 6,97 Gio (130 512 tokens, 31,9x à 4096), graphes CUDA 0,35 Gio ; `--gpu-memory-utilization 0.90` |
| `Qwen2.5-1.5B-Instruct` (FP16) | **14 860 MiB** / 16 384 | `0.90` réserve l'essentiel de la carte pour le cache KV, même pour un petit modèle |

La mémoire utilisée dépend surtout de `gpu-memory-utilization`, pas du modèle : le 1,5B n'occupe pas moins de GPU, il a juste plus de cache KV (voir la piste 6).

## 5. Résultats

Charge : `inference-perf` v0.7.0 depuis le pool système, via LiteLLM (clé virtuelle `lab-bench`) sauf mention « gateway » (Gateway Istio directe).
Profils synthétiques : prompts 128-1024 tokens (moyenne 512), sorties 64-256 (moyenne 128) ; `shared-prefix` : 4 préfixes de 1024 tokens x 16 utilisateurs ;
`long-prompt` : 2000-3500 tokens. « $/M tokens » = (nombre de GPU x 0,526 $/h) / (tokens de sortie/s x 3600) x 1e6, hors nœud système ; « tokens/J » = tokens de sortie par joule GPU (DCGM).

| Scénario | Profil | Cible | TTFT p50 (s) | TTFT p95 (s) | TPOT p50 (s) | TPOT p95 (s) | tok/s sortie | req/s | erreurs | GPU | $/M tokens | tokens/J | hit cache préfixes | W moyen | run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline-7b-keda | burst | litellm | 17.112 | 58.750 | 0.613 | 0.72 | 288.70 | 1.92 | 0 | 2.00 | 1.01 | 2.84 | 0.00 | 101.63 | 2026-11-17-baseline-7b-keda-burst |
| baseline-7b-load-only | shared-prefix | litellm | 0.142 | 0.322 | 0.032 | 0.04 | 288.70 | 1.98 | 0 | 2.00 | 1.01 | 2.38 | 0.98 | 121.14 | 2026-11-17-baseline-7b-load-only-shared-prefix-2replicas-load-only |
| baseline-7b | long-prompt | litellm | 102.110 | 228.811 | 3.146 | 3.25 | 3.38 | 0.13 | 71 | 1.00 | 43.20 | 0.06 | 0.00 | 60.52 | 2026-11-17-baseline-7b-long-prompt |
| baseline-7b | shared-prefix | litellm | 0.142 | 0.608 | 0.032 | 0.07 | 140.97 | 0.99 | 0 | 1.00 | 1.04 | 2.16 | 0.99 | 65.28 | 2026-11-17-baseline-7b-shared-prefix |
| baseline-7b | shared-prefix | litellm | 0.137 | 0.311 | 0.031 | 0.04 | 284.58 | 1.98 | 0 | 2.00 | 1.03 | 2.27 | 0.99 | 125.49 | 2026-11-17-baseline-7b-shared-prefix-2replicas-default |
| baseline-7b | smoke | litellm | 0.108 | 1.278 | 0.022 | 0.09 | 16.54 | 0.80 | 0 | 1.00 | 8.83 | 0.56 | - | 29.52 | 2026-11-17-baseline-7b-smoke |
| baseline-7b | steady | litellm | 0.628 | 1.571 | 0.049 | 0.07 | 145.95 | 0.96 | 0 | 1.00 | 1.00 | 2.28 | 0.00 | 64.14 | 2026-11-17-baseline-7b-steady |
| baseline-7b | steady | gateway | 0.578 | 1.346 | 0.058 | 0.10 | 139.52 | 0.96 | 0 | 1.00 | 1.05 | 2.20 | 0.00 | 63.42 | 2026-11-17-baseline-7b-steady-gateway |
| baseline-7b | sweep | litellm | 2.459 | 32.176 | 0.317 | 1.48 | 129.15 | 0.92 | 345 | 1.00 | 1.13 | 2.14 | 0.00 | 60.25 | 2026-11-17-baseline-7b-sweep |
| small-fp16 | long-prompt | litellm | 2.843 | 6.979 | 0.142 | 0.91 | 20.27 | 0.50 | 0 | 1.00 | 7.21 | 0.37 | 0.00 | 55.48 | 2026-11-17-small-fp16-long-prompt |
| small-fp16 | shared-prefix | litellm | 0.112 | 0.172 | 0.024 | 0.03 | 380.52 | 2.98 | 0 | 1.00 | 0.38 | 5.87 | 0.99 | 64.88 | 2026-11-17-small-fp16-shared-prefix |
| small-fp16 | steady | litellm | 0.226 | 0.463 | 0.034 | 0.05 | 435.93 | 2.97 | 0 | 1.00 | 0.34 | 6.90 | 0.00 | 63.22 | 2026-11-17-small-fp16-steady |
| small-fp16 | steady | gateway | 0.201 | 0.480 | 0.030 | 0.04 | 422.76 | 2.94 | 0 | 1.00 | 0.35 | 6.91 | 0.00 | 61.22 | 2026-11-17-small-fp16-steady-gateway |
| small-fp16 | sweep | litellm | 25.375 | 33.514 | 0.320 | 0.39 | 621.47 | 4.18 | 130 | 1.00 | 0.24 | 11.24 | 0.00 | 55.29 | 2026-11-17-small-fp16-sweep |

### Sweep (paliers de charge)

**baseline-7b (Qwen2.5-7B-Instruct-AWQ, 1 T4) - prompts 128-1024 tokens (moyenne 512), sorties 64-256 (moyenne 128)**

| Palier (req/s demandées) | Réussies | Échecs | TTFT p50 (s) | TTFT p95 (s) | TPOT p95 (s) | tok/s sortie | req/s servies |
|---|---|---|---|---|---|---|---|
| 0.5 | 45 | 0 | 0.52 | 1.63 | 0.05 | 63 | 0.47 |
| 1.0 | 90 | 0 | 0.68 | 2.19 | 0.14 | 131 | 0.94 |
| 1.5 | 135 | 0 | 1.02 | 3.38 | 0.27 | 186 | 1.30 |
| 2.0 | 180 | 0 | 2.40 | 4.21 | 0.76 | 209 | 1.47 |
| 3.0 | 270 | 0 | 19.19 | 39.19 | 1.54 | 222 | 1.54 |
| 4.0 | 15 | 345 | 4.51 | 6.55 | 1.71 | 8 | 0.13 |

**small-fp16 (Qwen2.5-1.5B-Instruct FP16, 1 T4) - mêmes distributions**

| Palier (req/s demandées) | Réussies | Échecs | TTFT p50 (s) | TTFT p95 (s) | TPOT p95 (s) | tok/s sortie | req/s servies |
|---|---|---|---|---|---|---|---|
| 2.0 | 0 | 120 | - | - | - | 0 | 0.00 |
| 4.0 | 230 | 10 | 0.39 | 5.59 | 0.10 | 542 | 3.50 |
| 8.0 | 480 | 0 | 1.40 | 15.17 | 0.37 | 765 | 5.05 |
| 12.0 | 720 | 0 | 22.95 | 33.28 | 0.41 | 761 | 5.17 |
| 16.0 | 960 | 0 | 26.53 | 33.34 | 0.40 | 754 | 5.11 |
| 24.0 | 1440 | 0 | 29.19 | 34.98 | 0.39 | 746 | 5.03 |


Lecture :
- **7B AWQ** : saturation entre 1,5 et 2 req/s (≈ 210-220 tokens/s de sortie). Sous SLO « TTFT p95 < 5 s », le débit maximal est **≈ 2 req/s** (palier 2 : p95 4,2 s).
  À 3 req/s la file explose (TTFT p50 19 s) ; à 4 req/s, 345 requêtes sur 360 échouent (voir anomalie 2).
- **1,5B FP16** : plateau à ≈ 5 req/s (≈ 750 tokens/s). Sous SLO « TTFT p95 < 5 s » : **≈ 4 req/s** (palier 4 : p95 5,6 s, légèrement au-dessus) ; le palier 8 est déjà saturé (p95 15 s).
  Le premier palier (2 req/s) est en échec total : il tombe pendant le redémarrage de LiteLLM après le changement de scénario (artefact, pas une mesure).
- Pendant les sweeps : utilisation GPU moyenne 71 % (7B) et 77 % (1,5B), **activité du moteur graphique 78-84 %**, activité DRAM seulement **16-22 %**, CPU vLLM ≤ 1,1 coeur :
  le goulot est le **calcul** (noyaux sans tensor cores), pas la bande passante mémoire ni le CPU.

## 6. Surcoût de LiteLLM et de la Gateway

| Scénario | TTFT p50 via LiteLLM | TTFT p50 direct Gateway | Écart | tokens/s sortie (LiteLLM / Gateway) |
|---|---|---|---|---|
| 7B AWQ, 1 req/s, 3 min | 0,628 s | 0,578 s | **+50 ms** | 146 / 140 |
| 1,5B FP16, 3 req/s, 5 min / 3 min | 0,226 s | 0,201 s | **+25 ms** | 436 / 423 |

Le TPOT client est plus faible via LiteLLM (explication probable, non vérifiée : regroupement des chunks SSE) : à lire avec prudence. LiteLLM consomme ~1 Gio au repos (OOM à 1,25 Gio sous 300+ flux, anomalie 3).
Le surcoût de la Gateway Istio elle-même n'est pas isolé (l'écart Gateway/direct vLLM nécessiterait un accès par IP de pod) ; sa latence p95 est visible dans le dashboard 01.

## 7. KEDA (`baseline-7b-keda`, 1 à 2 réplicas, 2 nœuds T4)

Profil `burst` (1 req/s pendant 60 s, puis 4 req/s pendant 240 s, puis 1 req/s). Chronologie (UTC, reconstruite depuis les événements Kubernetes et Prometheus) :

| Instant | Événement | Délai |
|---|---|---|
| 00:56:32 | démarrage du job de charge | 0 |
| 00:59:00-00:59:45 | file d'attente par pod : 0 -> 42 | |
| **00:59:29** | **décision de scale-out** (HPA : « New size: 2 ») | ~1-2 min après le début du pic |
| 01:00:13 | modèle téléchargé sur le 2e nœud (40 s) | |
| 01:03:44 | image vLLM (9 Go) tirée sur ce nœud pour la 1re fois (3 min 31) | |
| **01:06:20** | **2e pod Ready** (chargement + compilation 2 min 36) | **+6 min 51 après la décision** |
| **01:06:30** | **premier token servi par le nouveau réplica** | +10 s après Ready |
| 01:09:15 | retour à 1 réplica (« All metrics below target », cooldown 300 s) | |

Le délai de décision est court (polling 15 s) ; **le pod Ready est lent** (près de 7 min dont 3,5 min de pull d'image sur un nœud neuf). Avec l'image déjà présente, le délai serait ~3,3 min.
D'où : pas de scale-to-zero (piège F2) et fenêtre de scale-down de 5 min. KEDA, l'HPA et le ScaledObject sont créés par KServe (`spec.scaling.keda`).

## 8. Routage (2 réplicas, `shared-prefix`, 2 req/s, 5 min)

| EPP | TTFT p50 | TTFT p95 | hit cache de préfixes (pod A / pod B) | requêtes servies A / B |
|---|---|---|---|---|
| profil par défaut (affinité de préfixes + `token-load-scorer`) | 0,137 s | 0,311 s | 97,9 % / 98,1 % | 277 / 299 |
| charge seule (`token-load-scorer`) | 0,142 s | 0,322 s | 96,4 % / 95,4 % | 304 / 311 |

Avec 4 préfixes qui tiennent dans le cache des deux pods, l'affinité de préfixes n'apporte presque rien (**+2,5 points de hit ratio**, TTFT identique).
Les scorers `prefix-cache-scorer` / `load-aware-scorer` du prompt n'existent plus dans llm-d router v0.10 (D-09, D-26). Pour que l'écart devienne visible :
beaucoup plus de groupes de préfixes (> capacité du cache KV d'un pod) et/ou des préfixes plus longs.

## 9. Anomalies et pistes d'optimisation observées (classées par gain potentiel, rien n'est appliqué)

1. **Prefill sur T4 : attention Triton sans tensor cores** (gain potentiel : x5 à x15 sur `long-prompt`). Prompts de 2000-3500 tokens à 0,5 req/s : TTFT p50 **102 s**, 71 erreurs,
   débit de prefill ≈ 370 tokens/s ; le 1,5B tient (TTFT p50 2,8 s). Pistes : expérience A/B de version d'image (section 2), `max-num-batched-tokens`, prefill chunké, limiter la longueur des prompts, modèle plus petit pour les longs contextes.
2. **Saturation brutale du 7B au-delà de 2 req/s** : à 3 req/s TTFT p50 19 s, à 4 req/s 96 % d'erreurs (`ClientPayloadError`, connexions réinitialisées).
   Pistes : `max-num-seqs`, deuxième réplica (`gpu-scale 2` : 2 req/s servis sans file avec TTFT p50 0,14 s en `shared-prefix`, 288 tok/s), limiter la concurrence par équipe dans LiteLLM (rpm/tpm), timeouts.
3. **LiteLLM OOMKilled** à 3-4 req/s (limite 1,25 Gio, ~1 Gio au repos) : limite portée à 2 Gio (D-24). Piste : mesurer l'empreinte mémoire par flux, plusieurs workers.
4. **Cache KV sous-utilisé** : 130 512 tokens pour `max-model-len 4096` (31,9x de concurrence théorique) alors que le batch réel reste bien plus petit. Pistes : `max-num-seqs` plus élevé, `max-model-len` plus grand si les cas d'usage le demandent.
5. **Pool système juste** : `D4as_v7` à 75 % des requests CPU et 51 % des requests mémoire, mais les limites mémoire sont en sur-allocation de 267 % (OOM du nœud observé une fois). Piste : `D8as_v7` (+0,18 $/h) si l'on ajoute des composants, ou réduire Prometheus/LiteLLM.
6. **GPU mémoire** : le 1,5B occupe 14 860 MiB (`0.90`) : le modèle partage mal le GPU. Piste : scénario `gpu-sharing` (time-slicing, `gpu-memory-utilization` 0,45 chacun) pour héberger plusieurs petits modèles sur un T4.
7. **Efficacité énergétique** : ~60-65 W en charge (plafond 70 W), 2,2 tokens/J pour le 7B, 6,9 pour le 1,5B ; le coût par million de tokens de sortie vaut ≈ 1,0 $ (7B) et 0,34 $ (1,5B) à ~1 et 3 req/s.
   Le coût est dominé par l'utilisation : un nœud inactif coûte 0,526 $/h (alerte `LabGPUIdleCost` après 30 min).
8. **Cold start d'un 2e nœud GPU** : ~7 min jusqu'au pod Ready, dont le pull de l'image de 9 Go. Pistes : pré-tirer l'image (DaemonSet), disque d'images partagé, modèle sur un stockage local.
9. **Démarrage après `stop`** : les nœuds sont recréés (noms `vmss000002` / `000001`), donc driver recompilé et image retirée : ~16 min au total (`az aks start` 5 min 13).
10. **inference-perf v0.7.0** : le sweep automatique échoue (`index out of bounds`) ; le générateur synthétique n'accepte que `/v1/completions` ; pas de bloc `observability` (D-23).
11. **Faux positif de configuration** : l'image `llm-d-cuda:v0.9.0` livrée par KServe v0.21.0 n'a pas de noyau sm_75 (D-03), le driver ouvert (`kernel-open`) ne compile pas sur le noyau AKS 5.15 (D-18).

## 10. Critères d'acceptation

| # | Critère | État |
|---|---|---|
| 1 | `nvidia-smi` sur chaque T4, `nvidia.com/gpu: 1` par nœud | validé (2 nœuds) |
| 2 | Applications Argo CD Synced/Healthy ; self-heal | validé (scale à 0 annulé en 4 s) |
| 3 | `LLMInferenceService` Ready, Gateway Programmed, chat via LiteLLM (stream et non), test B5 | validé (`lab.sh smoke`) |
| 4 | Cibles Prometheus UP (DCGM, vLLM, EPP, Istio, LiteLLM, KEDA) | validé (36 cibles) |
| 5 | Jointure GPU / pod vLLM (labels du pod sur DCGM) | validé (`honorLabels`) |
| 6 | Aucun panneau vide après `bench steady` | validé (`tests/check_panels.py` : 59/59) |
| 7 | promtool, alerte de test jusqu'au récepteur, alerte de file | promtool : 5 tests ; alertes TTFT/inter-token/GPU inactif reçues par le récepteur |
| 8 | Logs vLLM et événements dans Loki/Grafana | validé sur kind (Loki) ; dashboard 05 |
| 9 | KEDA 1 -> 2 -> 1 avec délais | validé (section 7) |
| 10 | Routage : hit ratio avec/sans affinité | validé (section 8) |
| 11 | `stop`, `start`, `smoke` ; `down` ne laisse rien | validé ; `down` vérifié (groupes `inflab-rg` et `inflab-aks-nodes` supprimés) |
| 12 | Aucun secret dans Git (gitleaks) | **partiel** : aucun secret dans l'arbre de travail (états Terraform ignorés par Git), mais l'historique contient 2 clés virtuelles LiteLLM dans d'anciens `results/*/config.yaml` (le banc de charge écrivait `api_key` dans sa configuration). Les clusters concernés sont détruits : les clés sont invalides. `tests/static.sh` signale donc encore un échec gitleaks sur l'historique ; il disparaîtrait avec une réécriture de l'historique (force-push), non faite sans accord. Le banc masque désormais la clé dans ses résultats. |

Corrections apportées pendant le déploiement : voir `docs/DECISIONS.md` (D-17 à D-26).
