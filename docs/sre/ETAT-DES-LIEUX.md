# État des lieux - séance 1 (phase 0)

Date : 17/11/2026. Cluster : AKS `eastus`, 1 x T4 (`NC4as_T4_v3`), pool système `D4as_v7`.

> **Mise à jour (fin de séance 1, même jour, cluster réinstallé de zéro).** La séance 1 avait été interrompue par une destruction du cluster. Elle a été **complétée** sur un
> second cluster : bruit du 1,5B mesuré (section 3), changements d'industrialisation prouvés (section 5 bis), **constat n° 3 corrigé** (section 2). Les mentions « non fait »
> de la section 6 sont barrées ou annotées quand elles ont été traitées. Le texte d'origine est conservé pour la traçabilité.

## 1. Ce que le cluster était au départ

| Élément | État constaté |
|---|---|
| Versions | AKS 1.34, GPU Operator v26.7.2 (driver 580.95.05, modules propriétaires), KServe v0.21.0 + EPP llm-d v0.10.0, vLLM v0.32.0, Istio 1.30.8, LiteLLM v1.109.1, KEDA 2.21.1, Prometheus v3.16.0, Grafana 13.3.1, Loki 3.7.10, Argo CD v3.6.1 |
| Backend d'attention vLLM | `TRITON_ATTN` ; AWQ par `MarlinLinearKernel` (logs) |
| Cibles Prometheus | 36 cibles, toutes `up` ; règles lab chargées et saines |
| Dashboards | 12 provisionnés ; 59 panneaux Prometheus sur 59 avec données (`tests/check_panels.py`) |
| Smoke | 9/9 (Argo, Gateway, LLMInferenceService, GPU, chat T=0 / T=0,7 / streaming, cibles, règles) |
| Anomalies de `BASELINE.md` | traitées en début de séance : LiteLLM OOM (limite 2 Gio), `storage-initializer` OOM (6 Gio), pas de surge (rolloutStrategy). Restent ouvertes : prefill Triton, saturation du 7B, système juste, cold start |

## 2. Faits nouveaux établis pendant la séance

| # | Constat | Preuve | Conséquence |
|---|---|---|---|
| 1 | Les 4 vCPU du nœud GPU sont **4 cœurs physiques** (AMD EPYC 7V12, 1 thread par cœur) | `lscpu` dans le conteneur du driver | vLLM recommande 3 cœurs pour 1 GPU : la marge est de 1 cœur, dont ~0,9 est consommé par kubelet, DaemonSets et système |
| 2 | Le pod vLLM n'a **aucune limite CPU** (request 2,5 cœurs) | spec du pod | pas de throttling CFS possible ; `lab:vllm_cpu_throttled_ratio` n'a pas de série pour lui. Le CPU max mesuré est 1,1 cœur (sweep du 1,5B) : **le CPU n'a pas limité** les runs |
| 3 | ~~`SM_ACTIVE`, `SM_OCCUPANCY`, `PIPE_TENSOR_ACTIVE` ne sont pas exposées sur ce T4~~ **CORRIGÉ** : elles **sont exposées** (et non nulles) quand l'exporteur démarre avec la liste actuelle du ConfigMap. Cause **probable, non vérifiable** (le premier cluster est détruit) : l'exporteur tournait encore avec l'ancienne liste ; la documentation du GPU Operator indique que l'opérateur ne surveille pas ce ConfigMap (**doc**), il faut redémarrer le DaemonSet | cluster n° 2 : `DCGM_FI_PROF_SM_ACTIVE` 0,91, `SM_OCCUPANCY` 0,18, `PIPE_TENSOR_ACTIVE` 0,11, `PIPE_FP16_ACTIVE` 0,003 en charge (1,5B, 2 req/s) | les signaux nécessaires à V1/G1 existent ; voir [module 5 de la formation](../formation/05-lire-un-gpu.md) |
| 4 | Pendant une charge à 1 req/s sur le 7B : `GR_ENGINE_ACTIVE` ≈ 0,65 et `DRAM_ACTIVE` ≈ 0,26 | requête Prometheus pendant le run | moteur de calcul plus sollicité que la mémoire |
| 5 | L'attention Triton sur Turing est le goulot du prefill ; la PR de correction (#55380) est **ouverte**, dans aucune release | `gh api` | V1 devra tester **une version plus ancienne** (avant le bridage de FlashInfer sur sm_75) ou une image construite à partir de la PR (accord requis pour un fork) |
| 6 | Un nouveau nœud GPU coûte ~20 min avant d'être utile ; l'image vLLM n'est tirée qu'**après** le téléchargement du modèle | `tests/coldstart.py` | pré-tirage et GPU Operator en vague 1 codés (A3), **non retestés** |

## 3. Bruit de mesure (7B AWQ, `steady` à 1 req/s, boucle ouverte, échauffement de 60 s exclu, 300 s de mesure, 3 répétitions)

Outil : `tests/noise.py` (stage 1 de chaque run). Runs : `results/2026-11-17-baseline-7b-steady-noise-r{1,2,3}`.

| Métrique | médiane | écart-type | **CV (%)** | min - max |
|---|---|---|---|---|
| TTFT p50 (s) | 0,666 | 0,073 | **10,5** | 0,653 - 0,786 |
| TTFT p95 (s) | 1,95 | 0,63 | **29,1** | 1,65 - 2,86 |
| TPOT p50 (s) | 0,0696 | 0,0016 | **2,3** | 0,0678 - 0,0711 |
| TPOT p95 (s) | 0,131 | 0,027 | **18,7** | 0,126 - 0,174 |
| Latence p95 (s) | 23,5 | 5,8 | **22,0** | 22,7 - 33,2 |
| Tokens/s de sortie | 146 | 4,0 | **2,7** | 140,9 - 148,7 |
| Requêtes/s servies | 0,979 | 0,002 | **0,2** | 0,977 - 0,980 |
| Échecs | 0 | 0 | 0 | 0 |

**Lecture :**
- Les **débits** (tokens/s, req/s) sont très stables (CV <= 2,7 %) : un gain de débit de quelques pourcents est détectable.
- Les **latences en queue** (p95) sont bruyantes (CV de 19 à 29 %) : avec 3 répétitions, **aucun gain en p95 inférieur à ~50-60 % ne peut être déclaré** (≈ 2 écarts-types).
- Le TTFT p50 a 10,5 % de CV : seuil raisonnable de décision ≈ 20 %.
- **Limites de ce calcul** : 3 répétitions seulement (peu pour estimer une dispersion) ; un seul débit par modèle. Les seuils du 7B ne s'appliquent pas au 1,5B et inversement.
- **1,5B FP16 (mesuré sur le second cluster, `steady` à 2 req/s, mêmes 60 s d'échauffement + 300 s, 3 répétitions)** : CV tokens/s **0,7 %**, TTFT p50 **2,0 %**, TTFT p95 **6,9 %**, TPOT p50 **0,7 %**, TPOT p95 **4,9 %**, latence p95 **2,3 %** (médianes : 283 tok/s, TTFT p50 0,200 s, p95 0,416 s, TPOT p50 0,0256 s). Le 1,5B est **beaucoup moins bruyant** que le 7B, mais il tournait à ~40 % de sa capacité contre ~50-67 % pour le 7B : l'écart n'est pas attribuable au seul modèle. Détail : [module 1](../formation/01-mesurer-sans-se-tromper.md).
- Écart avec une mesure antérieure (BASELINE) : le `steady` de 3 minutes sans échauffement donnait TPOT p50 0,049 s et TTFT p50 0,628 s ; avec 60 s d'échauffement et 5 minutes, TPOT p50 0,070 s. Cause de l'écart **non élucidée** (durée, échauffement, état des caches du moteur : plusieurs pistes possibles). Règle retenue : ne **pas** comparer des runs de durée ou d'échauffement différents.

## 4. Instrumentation ajoutée (poussée dans Git ; non redéployée au moment de la destruction)

- DCGM : champs `SM_ACTIVE`, `SM_OCCUPANCY`, `PIPE_TENSOR_ACTIVE`, `PIPE_FP16_ACTIVE` demandés (exposés après redémarrage de l'exporteur, cf. constat 3 corrigé).
- Règles : `lab:vllm_cpu_cores`, `lab:vllm_cpu_throttled_ratio`, `lab:gpu_capacity`, `lab:gpu_allocatable`, `lab:gpu_allocated`, `lab:gpu_used` ; 3 panneaux dans le dashboard 02 (CPU vLLM vs activité GPU, throttling, GPU capacité/allouable/alloué/utilisé).
- Attribution GPU <-> pod : déjà en place (`honorLabels`, `enablePodLabels`).

## 5. Plan de campagne proposé (à valider)

Gain attendu sur le goodput de la classe concernée, coût estimé en heures de T4 (1 nœud GPU + système : 0,71 $/h ; 2 nœuds : 1,23 $/h). Les estimations d'heures supposent un démarrage de cluster d'~30 min à chaque séance.

| Priorité | ID | Expérience | Classe | Gain attendu | Coût (h GPU) | Dépendances / risques |
|---|---|---|---|---|---|---|
| 1 | V1 | Version d'image / backend d'attention sur `long-prompt` (+ config DCGM « tensor ») | RAG | **très élevé** (TTFT 102 s -> ? ; prefill x5-15 si FlashInfer revient) | 2-3 | image plus ancienne à identifier et à valider (noms de métriques, CUDA) ; fork = accord |
| 2 | V7 + G1 | CPU de vLLM et lecture des signaux GPU (à vide, prefill, decode, saturation) | toutes | faible (CPU non limitant) mais **déterminant pour la méthode** | 1 | peu coûteux : mesures existantes + 1 run |
| 3 | V3, V4 | `--max-num-seqs`, `--max-num-batched-tokens` (balayage, boucle fermée puis ouverte) | interactif, lot | moyen (compromis TTFT / ITL / débit) | 3-4 | chaque valeur = redémarrage du pod (~3 min, image en cache) |
| 4 | V2 | `--gpu-memory-utilization` (0.90 vs défaut vs `--kv-cache-memory`) | toutes | faible à moyen (stabilité, préemptions) | 1-2 | |
| 5 | M1, M2 | Quantization FP16/AWQ et taille 1,5B/7B (goodput par GPU, coût, qualité) | toutes | élevé (coût par token x3 entre 7B et 1,5B déjà observé) | 3-4 | exige le **contrôle de qualité** (30-50 prompts) à écrire |
| 6 | M3 | `max-model-len` 2048 / 4096 / 8192 | RAG | moyen | 1-2 | |
| 7 | A3 | Cold start : tester GPU Operator en vague 1 + pré-tirage (déjà codés) | toutes | **élevé en coût** (jusqu'à ~10 min de T4 par démarrage) | 1,5 (une réinstallation) | prouve les changements non testés |
| 8 | R1 | Routage : plus de groupes de préfixes que le cache n'en tient, 2 réplicas | multi-tour | moyen | 2-3 | **2 GPU** |
| 9 | A1 | KEDA : seuil 1, 2, 4 ; `pollingInterval`, `cooldownPeriod` | interactif | moyen (réactivité vs oscillations) | 2-3 | **2 GPU** |
| P1 | V5, V6, G2-G6, R2-R5, A2, A4-A5, P1-P4, M4-M6 | selon budget | | | | G2/G3 (partage GPU) : attribution DCGM à vérifier |

**Total P0 estimé : ~17-25 heures de T4**, soit ~12-18 $ avec 1 nœud (un peu plus pour les expériences à 2 nœuds). Ce sont des estimations, pas des engagements ; la séance 2 (SLO) ne demande presque pas de GPU.

## 5 bis. Preuve des changements d'industrialisation (second cluster, 17/11/2026)

Installation complète depuis un groupe de ressources vide (`lab.sh up`, aucune action manuelle) : **GPU Operator en vague 1 + pré-tirage de l'image + budget Azure** fonctionnent.
`terraform apply` 530 s ; budget Azure créé en 7 s (**pas refusé** par l'abonnement) ; 21 applications Argo CD Healthy à 17 min 57 s ; pod vLLM Ready à **18 min 55 s**
(28 min 46 s avant). Nœud GPU créé -> vLLM Ready : **721 s au lieu de 1 228 s** ; démarrage du driver 317 s au lieu de 590 s ; pull de l'image 1 s au lieu de 215 s. Détail et réserves
(le modèle a changé, 1,5B au lieu de 7B ; `lab.sh up` a planté sur un lien `kubectl` cassé et a dû être relancé) : [module 6](../formation/06-demarrage-a-froid.md).
Toujours **non testés sur cluster** : `lab.sh idle` et `lab.sh snapshot-metrics`.

## 6. Ce qui n'a PAS été fait dans cette séance (état d'origine ; voir la mise à jour en tête)

- ~~Répétitions du **1,5B** (bruit non mesuré)~~ **FAIT sur le second cluster** ; seule une répétition partielle a été lancée puis détruite.
- ~~Test des **ConfigMaps DCGM alternatives** (groupe « tensor »)~~ **sans objet** : la configuration existante suffit, le constat n° 3 était erroné.
- ~~Validation sur Azure des changements d'industrialisation~~ **FAIT** pour GPU Operator en vague 1, pré-tirage et budget Azure (section 5 bis) ; **reste non testé** : `lab.sh idle`, `lab.sh snapshot-metrics` (`tests/static.sh`, shellcheck, `terraform validate`).
- Heures GPU de la séance : ~1 h (04:14-05:12 environ) ; depuis le début du projet, le cluster a tourné ~6 h (dont ~40 min à 2 nœuds), soit un ordre de grandeur de **4 à 5 $** (estimation).

## 7. Décision attendue de l'utilisateur
Valider (ou modifier) la priorité du plan ci-dessus, puis passer à la séance 2 (classes de charge, SLO, burn rate), qui peut se faire presque sans GPU.
