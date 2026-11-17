# Sources : ce qu'on a lu, ce qu'on en a retenu, et à quel point on peut s'y fier

Recherche faite le 17/11/2026. Niveaux de confiance : **A** documentation ou code officiel lu directement · **B** article ou blog technique lu ou résumé · **C** relevé d'utilisateur sur un forum, non officiel · **D** connu seulement par un résumé de recherche (non relu en entier).
Les pages ont été lues par un outil qui en renvoie un **résumé** : les valeurs critiques (seuils, noms de champs) ont été recoupées avec le code source quand c'était possible.

## 1. Matériel et pilote

| # | Source | Niv. | Ce qu'on en a retenu | Utilisé dans |
|---|---|---|---|---|
| 1 | [Fiche NVIDIA du T4 (PDF, mars 2019)](https://www.nvidia.com/content/dam/en-zz/Solutions/Data-Center/tesla-t4/t4-tensor-core-datasheet-951643.pdf) | A | Turing, 2 560 coeurs CUDA, 320 tensor cores, 8,1 TFLOPS FP32, **65 TFLOPS** FP16/FP32, 130 TOPS INT8, 16 Go GDDR6 à **300 Go/s**, ECC oui, PCIe Gen3 x16, refroidissement passif, 70 W | 01, 02, figures |
| 2 | [en-tête `nvml.h` (dépôt go-nvml)](https://github.com/NVIDIA/go-nvml/blob/main/gen/nvml/nvml.h) | A | valeurs hexadécimales et descriptions des **raisons de bridage** (0x1 à 0x400) | 01, règles `lab:gpu_throttle_*` |
| 3 | [Documentation de nvidia-smi](https://docs.nvidia.com/deploy/nvidia-smi/index.html) (début de la page lu) | A | `-pl`, `-lgc`, sections `-q -d` (POWER, CLOCK, PERFORMANCE, TEMPERATURE, ECC, PAGE_RETIREMENT), `dmon -s pucvmet` ; sens des seuils de température | 01, 05 |
| 4 | [Azure NCasT4_v3](https://learn.microsoft.com/azure/virtual-machines/sizes/gpu-accelerated/ncast4v3-series) | A | 1 T4 de 16 Go pour `NC4as_T4_v3`, EPYC 7V12, disque OS éphémère supporté, migration à chaud non supportée | 01 |
| 5 | Fils du forum NVIDIA sur le T4 : [horloges d'application](https://forums.developer.nvidia.com/t/gpu-application-clock-and-warming-up-in-a-cuda-application/191842), [impossibilité de régler les horloges](https://forums.developer.nvidia.com/t/gomacs-cannot-change-application-clocks-for-tesla-t4/140786), [limite de puissance](https://forums.developer.nvidia.com/t/change-power-limitation-on-tesla-t4/72395) et plusieurs autres | **C** | horloges du T4 : repos 585 MHz, **maximum 1 590 MHz** (mémoire 5 001 MHz) ; seuils de température d'un T4 : **85 °C** (fonctionnement), **93 °C** (ralentissement), **96 °C** (arrêt) | 01, `gpuLimits` |

## 2. Mesure : DCGM, exporter, vLLM

| # | Source | Niv. | Ce qu'on en a retenu | Utilisé dans |
|---|---|---|---|---|
| 6 | [DCGM, vue d'ensemble des fonctions](https://docs.nvidia.com/datacenter/dcgm/latest/user-guide/feature-overview.html) (100 000 premiers caractères) | A | définitions de `SM_ACTIVE` (« 0,8 et plus nécessaire mais pas suffisant »), `DRAM_ACTIVE` (« maximum pratique ≈ 0,8 »), `PIPE_TENSOR_ACTIVE` ; échantillonnage 1 Hz ; droits admin et conflit avec Nsight ; `dcgmi health` | 01, 02, 05 |
| 7 | [DCGM, diagnostics](https://docs.nvidia.com/datacenter/dcgm/latest/user-guide/dcgm-diagnostics.html) | A | niveaux r1 à r4 et leurs tests ; durées mesurées sur Hopper ; le test de déploiement échoue si un autre processus graphique utilise le GPU | 05 |
| 8 | [DCGM, injection d'erreurs](https://docs.nvidia.com/datacenter/dcgm/latest/user-guide/dcgm-error-injection.html) | **D** | `dcgmi test --inject --gpuid <n> -f <champ> -v <valeur>` ; réservé à un hôte de test ; champ 230 = XID (d'après le guide EKS) ; la valeur persiste jusqu'au remplacement du nœud | 05 (S9) |
| 9 | [dcgm-exporter, `default-counters.csv` du tag 4.8.4](https://github.com/NVIDIA/dcgm-exporter/blob/4.8.4/etc/default-counters.csv) | A | **noms valides** de la version déployée (fixture `tests/fixtures/`) ; unité des champs de violation : « ns » dans l'aide | 01, config GPU Operator |
| 10 | [dcgm-exporter, `default-counters.csv` de `main`](https://github.com/NVIDIA/dcgm-exporter/blob/main/etc/default-counters.csv) | A | **piège** : la branche `main` utilise d'autres noms (`DCGM_FI_DEV_GPU_TEMP_CELSIUS`, `..._BOARD_POWER_WATTS`...) ; ne pas s'y fier pour notre version | 01 |
| 11 | [vLLM, métriques de production](https://docs.vllm.ai/en/stable/usage/metrics.html) et [`arg_utils.py` au tag v0.32.0](https://github.com/vllm-project/vllm/blob/v0.32.0/vllm/engine/arg_utils.py) | A | `vllm:estimated_flops_per_gpu_total`, `..._read_bytes_...`, `..._write_bytes_...` « disponibles via `--enable-mfu-metrics` » ; le drapeau existe dans v0.32.0 (vérifié dans le code) | 01, 02, scénario `gpu-health` |

## 3. Santé et dépannage

| # | Source | Niv. | Ce qu'on en a retenu | Utilisé dans |
|---|---|---|---|---|
| 12 | [Catalogue XID de NVIDIA](https://docs.nvidia.com/deploy/xid-errors/analyzing-xid-catalog.html) | A | nom, cause probable et action pour les XID 13, 31, 43, 45, 48, 63, 64, 74, 79, 94, 95, 119, 120 ; XID 63 : retrait de pages avant l'A100, remappage de lignes ensuite | 04, runbooks |
| 13 | [Travailler avec les XID](https://docs.nvidia.com/deploy/xid-errors/working-with-xid-errors.html) | A | format `NVRM: Xid (0000:03:00): 14, ...` dans le journal du noyau | 04 |
| 14 | [Guide de triage d'un nœud GPU](https://docs.nvidia.com/deploy/gpu-debug-guidelines/gpu-node-triage.html) | A | ordre d'intervention ; **sur une VM le reset du GPU est souvent non supporté** ; `dcgmi diag -r 3` ≈ 30 min ; les seuils de RMA n'étaient pas dans le texte lu | 04 |
| 15 | [AKS : surveillance de la santé des GPU (NPD)](https://learn.microsoft.com/en-us/azure/aks/gpu-health-monitoring) (mise à jour du 09/11/2026) | A | liste des contrôles (GPUMissing, XID, bridage, ECC...) ; **ne s'applique pas aux pools `--gpu-driver none`** ; NPD ne remédie à rien | 02, 05, 06 |
| 16 | [NVSentinel (NVIDIA)](https://github.com/NVIDIA/NVSentinel) | A | modules ; installation en observation seule par défaut ; prérequis : Kubernetes 1.34+, cert-manager 1.21+, GPU Operator avec `dcgm.enabled`, MongoDB ; **architectures validées : Volta, Ampere, Hopper, Ada, Blackwell** | 05 |
| 17 | [AKS : métriques GPU](https://learn.microsoft.com/azure/aks/monitor-gpu-metrics) | D | `DCGM_FI_DEV_XID_ERRORS` devrait rester à zéro | 01, 02 |

## 4. Performance et efficacité

| # | Source | Niv. | Ce qu'on en a retenu | Utilisé dans |
|---|---|---|---|---|
| 18 | [Databricks : LLM Inference Performance Engineering](https://www.databricks.com/blog/llm-inference-performance-engineering-best-practices) | B | définition du **MBU** = (poids + cache KV) ÷ TPOT ÷ bande passante de pointe ; le décodage est limité par la mémoire | 01, 02 |
| 19 | [A. Chiao : utilisation contre saturation](https://arthurchiao.art/blog/understanding-gpu-performance) | B | NVML mesure un **temps d'occupation** ; méthode USE ; préférer les compteurs DCGM de profilage | 01, README |
| 20 | [NVIDIA : concepts fondamentaux du benchmarking de LLM](https://developer.nvidia.com/blog/llm-benchmarking-fundamental-concepts) | D | TTFT inclut file, prefill et réseau ; TPOT = temps entre tokens (sans le TTFT) | 02 |
| 21 | [GreenLLM, arXiv 2508.16449](https://arxiv.org/abs/2508.16449) | B | jusqu'à **34 %** d'énergie en moins, moins de 3,5 % de violations de SLO en plus (traces Alibaba et Azure) | 04 |
| 22 | [VoltanaLLM, arXiv 2509.04827](https://arxiv.org/pdf/2509.04827v1) ; [RAPID, arXiv 2601.12241](https://arxiv.org/pdf/2601.12241) ; [HALO, CEUR vol. 4275](https://ceur-ws.org/Vol-4275/paper18.pdf) | **D** | baisser les horloges ne réduit pas toujours l'énergie ; partage de puissance prefill / decode ; 39,4 % d'énergie GPU en moins par calibration | 04 |

## 5. Référentiel de compétences

| # | Source | Niv. | Ce qu'on en a retenu | Utilisé dans |
|---|---|---|---|---|
| 23 | [NVIDIA-Certified Professional: AI Operations](https://www.nvidia.com/en-us/learn/certification/ai-operations-professional) | A (résumé par l'outil) | domaines et pondérations (31 / 23 / 23 / 23 %) ; responsabilités clés ; le GPU Operator n'est pas cité | 06 |

## 6. Écarts, corrections et incertitudes (à lire)

1. **Bande passante du T4 : 300 ou 320 Go/s ?** La fiche de 2019 dit 300 ; d'autres documents NVIDIA disent 320. Les docs du lab disaient « 320 Go/s (fiche NVIDIA) » : c'était **inexact** pour cette fiche. On garde 320 pour les bornes théoriques et on note l'écart de 6 % (le MBU de 83 % devient 88 % avec 300).
2. **Horloge maximale (1 590 MHz) et seuils thermiques (85, 93, 96 °C)** : les docs précédentes les attribuaient à « la fiche NVIDIA » ; ils viennent en réalité de relevés sur le **forum NVIDIA** (niveau C). Corrigés dans le guide et le module 5. **Confirmés le 17/11/2026** par `nvidia-smi -q` sur notre GPU : valeurs exactes (niveau **observé**).
3. **Unité des compteurs de violation** (`DCGM_FI_DEV_POWER_VIOLATION`, `..._THERMAL_VIOLATION`) : « ns » dans le fichier du tag 4.8.4, « µs » dans d'autres versions de la documentation. **Tranché le 17/11 par déduction** : le compteur a valu 60 355 136 après le run à 60 W alors que `nvidia-smi dmon` (pourcentage entier à 1 Hz) affichait 0 sur tout le run ; en µs cela ferait 60 s (19 % du temps), `dmon` l'aurait vu : c'est donc des **nanosecondes**. Déduction, pas confirmation par la documentation. Ce compteur **ne voit pas** le plafond logiciel (0 alors que le bit `0x4` est actif).
4. **Noms de champs DCGM selon la version** : `main` utilise de nouveaux noms ; notre version 4.8.4 les anciens. Tout nom ajouté est vérifié par `tests/check_dcgm_fields.py` contre le fichier du tag 4.8.4. **Les 9 champs de santé ajoutés ont tous été observés sur le cluster le 17/11/2026** ; `DCGM_FI_DEV_XID_ERRORS` n'existe qu'à partir de la première erreur (absent avant l'injection).
5. **Durée de `dcgmi diag -r 3`** : « moins de 10 min pour 4 GPU Hopper » (doc DCGM) contre « environ 30 min » (guide de triage). **Mesuré sur T4, GPU libre : 348 s (5 min 48)** ; niveau 2 : 10 s.
6. **`nvidia-smi -pl` sur T4** : aucune source consultée ne confirmait qu'il fonctionne (un [fil du forum](https://forums.developer.nvidia.com/t/change-power-limitation-on-tesla-t4/72395) affirme seulement que le T4 est alimenté par le bus). **Testé le 17/11 sur la VM Azure : `-pl 60` et `-pl 65` fonctionnent**, ainsi que `-lgc 900,900` et `-lgc 750,750` ; `-ac` non testé.
7. **Les pondérations de l'examen** : lues sur la page officielle par un outil de résumé ; d'autres sources donnent d'autres répartitions et un autre format d'épreuve. **Vérifier sur la page officielle.**
8. **Reste sans mesure du lab** : une charge soutenue de plus de 50 minutes, deux GPU comparés, un balayage d'horloge à 5 fréquences avec decode et prefill séparés, l'efficacité à faible débit. **Mesuré depuis** : le masque de bridage (valeurs 0, 1, 4), les champs de santé, l'estimation MFU de vLLM (≈ 0,3 TFLOPS, MBU ≈ 0,10 : **non fiable**, 7 fois sous le calcul).
9. **Sources Istio** : l'annonce officielle de l'arrêt de `registry.istio.io`, `gcr.io/istio-release` et `istio-release.storage.googleapis.com` (arrêt définitif le 16/12/2026, coupures de test dont le 17/11 de 15 h à 21 h UTC) est lue sur [istio.io](https://istio.io/latest/blog/2026/retirement-of-gcp/) (niveau **A**, résumée par l'outil de lecture de pages) ; les nouveaux emplacements (`blob.istio.io/istio-release/charts`, `docker.io/istio`) ont été **vérifiés** sur le cluster ([D-41](../DECISIONS.md)).
