# 05 - Le GPU T4 : ce qu'il permet, ce qu'il interdit, comment le lire

## 1. La carte

| Caractéristique | Valeur | Source |
|---|---|---|
| GPU | NVIDIA Tesla T4, architecture **Turing**, compute capability **7.5** | (observé) `nvidia-smi` : `Tesla T4`, `modelName` DCGM |
| VRAM | 16 384 MiB (15,56 GiB utilisables vus par vLLM) | (observé) |
| Bande passante mémoire | 320 Go/s | fiche produit NVIDIA (doc) |
| Puissance maximale | 70 W | (observé) `nvidia-smi` : `70W` ; la consommation en charge reste à 60-65 W |
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

Quatre signaux DCGM, à lire **ensemble** (dashboard 02) :

| Signal | Ce qu'il mesure vraiment | Piège |
|---|---|---|
| `DCGM_FI_DEV_GPU_UTIL` | part du temps où **au moins un noyau** tournait | rapport cyclique : 100 % ne veut pas dire « saturé » |
| `DCGM_FI_PROF_GR_ENGINE_ACTIVE` | part du temps où le moteur graphique est occupé | meilleur indicateur de charge de calcul sur T4 |
| `DCGM_FI_PROF_DRAM_ACTIVE` | part du temps où l'interface mémoire est active | proche de 1 = limité par la bande passante (decode) |
| `DCGM_FI_DEV_POWER_USAGE` | puissance instantanée | proche de 70 W = plafond énergétique |

Valeurs lues sur ce lab pendant les sweeps (**observé**) : utilisation moyenne 71 % (7B) et 77 % (1,5B), moteur actif 78-84 %, DRAM active 16-22 %, puissance 55-65 W.
Interprétation : **calcul** saturé, mémoire peu sollicitée, énergie proche du plafond. Le T4 est ici limité par ses unités de calcul et son budget de puissance, pas par sa mémoire.

## 4. Les trois états d'un GPU d'inférence

| État | GPU_UTIL | ENGINE_ACTIVE | DRAM_ACTIVE | Puissance |
|---|---|---|---|---|
| Au repos, modèle chargé | 0 | 0 | ~0 | ~30 W (observé 28-31 W) |
| Charge modérée (1 req/s, 7B) | non relevé | 65 % (observé) | 26 % (observé) | ~60-65 W |
| Saturation | 70-100 % | 78-84 % | 16-22 % | 60-65 W (plafond 70 W) |

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
Mesuré : CPU de vLLM <= 1,1 cœur pendant les sweeps (**observé**), donc le CPU n'était pas le goulot dans ces runs. À re-vérifier à fort débit de streaming.

## 7. Ce qu'un GPU plus récent changerait (raisonnement, non déployé)

- **bfloat16 et FP8** : modèles plus gros en moins de mémoire, noyaux de calcul plus rapides.
- **FlashAttention / FlashInfer** : le prefill sur prompts longs retrouverait les tensor cores : le problème du `long-prompt` disparaîtrait.
- **MIG** (A100/H100 et autres) : partage avec isolation matérielle.
- **Plus de bande passante** : decode plus rapide (le T4 a 320 Go/s ; les générations suivantes ont plusieurs fois plus).
Ces points sont des conséquences connues des spécifications, pas des mesures de ce lab.
