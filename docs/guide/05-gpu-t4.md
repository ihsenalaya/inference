# 05 - Le GPU T4 : ce qu'il permet, ce qu'il interdit, comment le lire

Pour aller plus loin (santé du GPU, KPI, dashboards, arbres de décision, séance de mesures) : le [dossier docs/gpu](../gpu/README.md).

Le GPU est la pièce chère du lab (0,526 $/h) et celle qui borne tout : sa **mémoire** décide quel modèle tient, sa **puissance de calcul** décide combien de requêtes par seconde passent.
Ce chapitre présente la carte, ce qu'elle ne sait pas faire, et comment lire ses compteurs sans se tromper.

<!-- mots: nvidia t4, compute capability, tensor core, vram, dcgm, gpu_util, throttling, xid -->
> **Mots à connaître**
> - **NVIDIA T4** : Le GPU du lab : architecture Turing, 16 Go, 70 W maximum, pas de bf16 ni FP8. Peu cher, peu puissant.
> - **Compute capability** : Numéro de génération d'un GPU (T4 = 7.5). Il décide des fonctions disponibles.
> - **Tensor core** : Unité du GPU spécialisée en multiplications de matrices, très rapide pour l'IA.
> - **GPU / VRAM** : Le processeur de calcul (ici un NVIDIA T4) et sa mémoire (16 Go). Le modèle et le cache KV doivent y tenir.
> - **DCGM** : Outil NVIDIA qui mesure le GPU ; `dcgm-exporter` publie ces mesures pour Prometheus.
> - **GPU_UTIL** : Part du temps où *au moins un* calcul tournait. **100 % ne veut pas dire saturé** (observé : le même GPU passe de 284 à 933 tokens/s à `GPU_UTIL` constant ou plus bas).
> - **Throttling / limite de puissance** : Le GPU baisse sa fréquence quand il atteint sa limite (70 W sur T4).
> - **XID** : Code d'erreur NVIDIA signalant un problème GPU (ex. 79 : GPU tombé du bus).
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## 1. La carte

| Caractéristique | Valeur | Source |
|---|---|---|
| GPU | NVIDIA Tesla T4, architecture **Turing**, compute capability **7.5** | (observé) `nvidia-smi` : `Tesla T4`, `modelName` DCGM |
| VRAM | 16 384 MiB (15,56 GiB utilisables vus par vLLM) | (observé) |
| Bande passante mémoire | **320 Go/s** (la fiche NVIDIA de mars 2019 indique **300 Go/s**) | documents NVIDIA (doc) ; écart détaillé dans [docs/gpu/SOURCES.md](../gpu/SOURCES.md) |
| Puissance maximale | 70 W | (observé) `nvidia-smi` : `70W` ; la consommation en charge atteint 58 à 68 W selon la charge (observé le 17/11) |
| Tensor cores FP16 | jusqu'à 65 TFLOP/s | fiche produit NVIDIA (doc) |
| VM Azure | `Standard_NC4as_T4_v3` : 4 vCPU (4 **cœurs**, 1 thread/cœur, AMD EPYC 7V12), 28 Gio, disque temporaire de 180 Go | (observé) `lscpu` |
| Driver / CUDA | 580.95.05 / 13.0 | (observé) `nvidia-smi` |

## 2. Ce que Turing ne sait pas faire

| Absent | Conséquence dans ce lab |
|---|---|
| **bfloat16** | on impose `--dtype float16` (en bf16, vLLM refuse ou émule). Les modèles instables en FP16 (ex. Gemma 3) sont exclus |
| **FP8** (calcul et cache KV) | pas de quantization FP8 ; le cache KV en FP8 n'est pas disponible avec le backend Triton |
| **FlashAttention 2/3** | exige compute capability >= 8.0 (log vLLM : `FA2 is only supported on devices with compute capability >= 8`) |
| **MIG** (partition matérielle du GPU) | absent ; le partage passe par time-slicing ou MPS |
| tensor cores utilisés par l'attention Triton | depuis Triton 3.3 sur Turing : issue vLLM #60821 (doc) ; effet mesuré : prefill très lent sur prompts longs |

Quantizations supportées sur Turing d'après la doc vLLM consultée : AWQ, GPTQ, Marlin (hors MXFP4), INT8 W8A8. Nous utilisons **AWQ + Marlin** (observé dans les logs).

## 3. Lire un GPU en inférence

Quatre signaux DCGM de base, à lire **ensemble** (dashboard 02), puis les compteurs de profilage fins ajoutés le 17/11 :

| Signal | Ce qu'il mesure vraiment | Piège |
|---|---|---|
| `DCGM_FI_DEV_GPU_UTIL` | part du temps où **au moins un noyau** tournait | rapport cyclique : 100 % ne veut pas dire « saturé » |
| `DCGM_FI_PROF_GR_ENGINE_ACTIVE` | part du temps où le moteur graphique est occupé | meilleur indicateur de charge de calcul sur T4 |
| `DCGM_FI_PROF_DRAM_ACTIVE` | part du temps où l'interface mémoire est active | proche de 1 = limité par la bande passante (decode) |
| `DCGM_FI_DEV_POWER_USAGE` | puissance instantanée | proche de 70 W = plafond énergétique |
| `DCGM_FI_PROF_SM_ACTIVE` | part du temps où au moins un groupe de threads (warp) tourne sur une unité de calcul (SM), en moyenne sur les SM | plus fin que `GPU_UTIL` ; 0,88 à 0,97 en charge (observé) |
| `DCGM_FI_PROF_PIPE_TENSOR_ACTIVE` | part du temps où les tensor cores travaillent | 0,04 à 0,14 avec le 1,5B FP16, **0,28 à 0,32 avec le 7B AWQ** (observé) |

Valeurs lues sur ce lab pendant les sweeps (**observé**) : utilisation moyenne 71 % (7B) et 77 % (1,5B), moteur actif 78-84 %, DRAM active 16-22 %, puissance 55-65 W.
Interprétation : **calcul** saturé, mémoire peu sollicitée, énergie proche du plafond. Le T4 est ici limité par ses unités de calcul et son budget de puissance, pas par sa mémoire.

## 4. Les trois états d'un GPU d'inférence

| État | GPU_UTIL | ENGINE_ACTIVE | DRAM_ACTIVE | Puissance |
|---|---|---|---|---|
| Au repos, modèle chargé | 0 | 0 | ~0 | ~30 W (observé 28-31 W) |
| Charge modérée (1 req/s, 7B) | non relevé | 65 % (observé) | 26 % (observé) | ~60-65 W |
| Saturation | 70-100 % | 78-84 % | 16-22 % | 60-65 W (plafond 70 W) |

Valeurs relevées le 17/11 sur le cluster n° 2, détail et interprétation : [module 5 de la formation](../formation/05-lire-un-gpu.md). Exemples : à vide 30,6 W et horloge 585 MHz ; interactif 1,5B à 2 req/s `GPU_UTIL` 100 %, 68 W, 1 142 MHz ;
lot 1,5B saturé `GPU_UTIL` 83 %, 933 tokens/s au lieu de 284 : **`GPU_UTIL` à 100 % ne signifie pas « saturé »**.

Un GPU **alloué mais inactif** coûte le même prix (0,526 $/h par T4) : c'est pourquoi une alerte `LabGPUIdleCost` se déclenche après 30 minutes d'inactivité et pourquoi `lab.sh stop` existe.

## 5. La santé du GPU (ce qu'on surveille)

| Signal | Alerte | Que faire |
|---|---|---|
| `DCGM_FI_DEV_XID_ERRORS` > 0 | `LabGPUXidError` (critique) | consulter la table XID de NVIDIA ; XID 79 (GPU tombé du bus) = remplacer le nœud |
| `DCGM_FI_DEV_GPU_TEMP` | `LabGPUTemperatureHigh` (> 85 °C) | réduire la charge ; en cas de récurrence, remplacer le nœud |
| `DCGM_FI_DEV_CLOCK_THROTTLE_REASONS` | `LabGPUThrottling` | puissance ou thermique : relire la table des raisons |
| `DCGM_FI_DEV_ECC_*` | (à ajouter) | erreurs mémoire |
| `DCGM_FI_DEV_FB_USED/FREE` | `LabGPUMemoryHigh` (> 95 %) | OOM CUDA imminent (rare : vLLM préalloue) |

Détail des procédures (cordon, drain, remplacement, montée de driver) : phase « opérations GPU » du plan de campagne (non encore menée sur ce lab).

## 6. Le CPU, partenaire du GPU

vLLM a besoin de CPU pour tokeniser, servir l'API et streamer. Recommandation vLLM : 2 + N cœurs **physiques** pour N GPU, soit 3 pour 1 GPU (doc).
Ici : 4 cœurs physiques (observé), dont ~0,9 consommé par les DaemonSets, kubelet et le système (requests de 2 865 m sur 3 860 m allouables avec le pod vLLM à 2 500 m).
Le pod vLLM **n'a pas de limite CPU** (seulement une request de 2,5 cœurs) : pas de throttling CFS possible.
Mesuré : CPU de vLLM <= 1,1 cœur pendant les sweeps et **0,16 à 0,36 cœur en moyenne** sur les runs du 17/11, y compris en saturation (**observé**), donc le CPU n'était pas le goulot dans ces runs (une moyenne sur 5 minutes peut cacher des pics).

## 7. Ce qu'un GPU plus récent changerait (raisonnement, non déployé)

- **bfloat16 et FP8** : modèles plus gros en moins de mémoire, noyaux de calcul plus rapides.
- **FlashAttention / FlashInfer** : le prefill sur prompts longs retrouverait les tensor cores : le problème du `long-prompt` disparaîtrait.
- **MIG** (A100/H100 et autres) : partage avec isolation matérielle.
- **Plus de bande passante** : decode plus rapide (le T4 a 300 à 320 Go/s selon les documents NVIDIA ; les générations suivantes ont plusieurs fois plus).
Ces points sont des conséquences connues des spécifications, pas des mesures de ce lab.
