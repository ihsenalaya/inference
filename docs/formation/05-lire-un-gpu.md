# Module 5 - Lire un GPU en inférence : ce que disent (et ne disent pas) les compteurs du T4

**Objectif** : savoir lire les compteurs DCGM d'un GPU pendant l'inférence, et ne plus confondre « GPU utilisé à 100 % » avec « GPU saturé ».
Toutes les valeurs ci-dessous sont des **moyennes sur la fenêtre de mesure** de runs réels du lab (`tests/run_window.py`, Prometheus), 1 x T4.
Marques de fiabilité : voir [le guide](../guide/README.md).

## 1. Le concept en dix lignes

1. `DCGM_FI_DEV_GPU_UTIL` est un **rapport cyclique** : la part du temps où **au moins un noyau** tournait. Un seul petit noyau qui occupe 1 SM sur 40
   donne 100 %. Ce n'est pas un taux de travail.
2. `DCGM_FI_PROF_GR_ENGINE_ACTIVE` : part du temps où le moteur graphique/calcul est actif (proche d'`UTIL`, mesuré par les compteurs de profilage).
3. `DCGM_FI_PROF_SM_ACTIVE` : part du temps où **au moins un warp** est actif sur un SM, moyennée sur les SM. Plus fin qu'`UTIL`.
4. `DCGM_FI_PROF_SM_OCCUPANCY` : warps **résidents** rapportés au maximum possible. Faible = peu de parallélisme exposé.
5. `DCGM_FI_PROF_PIPE_TENSOR_ACTIVE` : part du temps où le pipeline des **tensor cores** est actif.
6. `DCGM_FI_PROF_DRAM_ACTIVE` : part des cycles où la mémoire GPU échange des données (le decode est limité par cette bande passante).
7. Puissance, horloge SM, température : un T4 est limité à **70 W** ; près du plafond, le GPU **baisse son horloge**.

## 2. Ce que le lab expose (config)

`gitops/platform/gpu-operator/values.yaml` : le ConfigMap `dcgm-metrics` liste les champs ci-dessus. **Piège (doc)** : l'opérateur ne surveille pas ce
ConfigMap ; un changement n'est pris en compte qu'au **redémarrage du DaemonSet de l'exporteur**. C'est la **cause probable** (non vérifiable : le premier cluster est détruit) pour laquelle la séance 1 avait conclu à tort que
`SM_ACTIVE`, `SM_OCCUPANCY` et `PIPE_TENSOR_ACTIVE` « ne sont pas exposés » sur le T4 : l'exporteur tournait avec l'ancienne liste. Sur un cluster
installé avec la liste actuelle, **les compteurs sont exposés et non nuls** (vérifié en charge : `SM_ACTIVE` 0,91, `PIPE_TENSOR_ACTIVE` 0,11).

## 3. Les chiffres : un GPU vu dans cinq situations (observé, 1,5B FP16, vLLM v0.32.0, attention `TRITON_ATTN`)

| Situation | GPU_UTIL | SM_ACTIVE | SM_OCC. | TENSOR | DRAM | Puissance | Horloge SM | KV | Requêtes en cours |
|---|---|---|---|---|---|---|---|---|---|
| **À vide** | 0 % | 0 | 0 | 0 | ~0 | **30,6 W** | **585 MHz** | 0 | 0 |
| Interactif, 2 req/s (prompts courts, decode dominant) | **100 %** | 0,88 | 0,13 | 0,086 | 0,70 | 68,0 W | 1 142 MHz | 0,7 % | 5 |
| `steady` 2 req/s (3 répétitions) | 94-100 % | 0,84-0,90 | 0,14-0,18 | 0,096-0,122 | 0,53-0,60 | 66-68 W | 1 142-1 203 MHz | ~2 % | 6-7 |
| **RAG** 0,5 req/s (prompts de 2 000-3 500 tokens, prefill dominant) | **72 %** | 0,79 | **0,26** | **0,07** | **0,15** | 58,2 W | **1 383 MHz** | 14 % | 6 (0,8 en attente) |
| **Lot**, 7 req/s demandés (saturation) | 83 % | 0,81 | 0,22 | **0,14** | 0,21 | 59,8 W | 1 116 MHz | **52 %** | **200** (89 en attente) |
| Multi-tour 0,5 req/s (cache de préfixes à 82 %) | 61 % | 0,62 | 0,28 | 0,04 | 0,43 | 59,0 W | 1 200 MHz | 3,5 % | 2 |

Runs : `results/2026-11-17-small-fp16-{interactive,long-prompt,batch,multi-turn}-class`, `...-steady-noise-r{1,2,3}`. Fichier par run : `server_window.json`.

## 4. Lecture guidée

### a. « 100 % utilisé » ne veut pas dire « saturé »
À 2 req/s en interactif, `GPU_UTIL` vaut **100 %** : on est pourtant à environ 40 % de la capacité du 1,5B. La preuve est dans la ligne « lot » : en
lui envoyant 7 req/s, le **même GPU** produit **933 tokens/s au lieu de 284** (x3,3) avec un `GPU_UTIL` **plus bas** (83 %). Un compteur qui reste à 100 % alors que
le débit peut encore tripler ne mesure pas la marge. Pour juger la saturation, regardez la **file** (`requests_waiting`), le **cache KV** et le **débit obtenu face au débit
demandé**, puis `SM_ACTIVE` et `DRAM_ACTIVE` pour savoir de quelle ressource le GPU manque.

### b. Le prefill et le decode n'usent pas le GPU de la même façon
- **Decode dominant** (interactif) : la mémoire travaille beaucoup (`DRAM_ACTIVE` 0,70) car chaque token relit les poids ; `SM_OCCUPANCY` est bas (0,13).
- **Prefill dominant** (RAG) : `DRAM_ACTIVE` s'effondre à 0,15, `SM_OCCUPANCY` monte (0,26), et **`PIPE_TENSOR_ACTIVE` est le plus bas** des cinq situations (0,07).
  Conséquence directe observée côté utilisateur : le **TPOT p50 passe de 0,020 s (interactif) à 0,20 s (RAG)** : un prefill de ~2 750 tokens bloque le decode des
  autres requêtes de la même fenêtre de calcul. **Des prompts longs dégradent la latence inter-token de tous les autres utilisateurs.**

### c. Les tensor cores travaillent... un peu
Hypothèse de départ de la campagne : « l'attention Triton sur Turing n'utilise pas les tensor cores, donc le prefill est lent ». Observation : `PIPE_TENSOR_ACTIVE`
n'est **pas nul** (0,04 à 0,14), donc des opérations passent bien par les tensor cores (probablement les multiplications de matrices ; **cause non vérifiée**). Il est **le plus bas
pendant le prefill long** (0,07), ce qui est **cohérent** avec un noyau d'attention sans tensor cores qui domine ce régime, **sans le démontrer** : ce sont des
moyennes sur 5 minutes de charges mixtes, pas une mesure isolée du prefill. Le test propre (V1) reste à faire avec une charge de prefill pur.

### d. Le T4 est limité par sa puissance, pas par sa température
À vide : 30,6 W et 585 MHz (horloge de repos). En charge interactive : **68 W sur 70 W** et **1 142 MHz** (le T4 monte à 1 590 MHz au maximum selon la fiche NVIDIA, **doc** : 72 %).
Pendant le RAG (58 W), l'horloge reste plus haute (1 383 MHz). Température en charge : 52 à 68 degrés Celsius, loin des 85 de l'alerte. **Le plafond de puissance de 70 W
borne le débit** : c'est un autre rappel que le T4 n'est pas un GPU de performance.

### e. Le CPU n'est pas le goulot
`vllm_cpu_cores` : 0,18 à 0,36 coeur moyen, y compris en saturation, pour un nœud de 4 coeurs. La contention CPU, suspecte n° 1 du plan, **n'est pas observée** dans ces
runs (une moyenne de 270 s peut cacher des pics, mais le CPU n'a jamais limité le débit).

## 5. À retenir

1. `GPU_UTIL` = « un noyau tourne ». Jugez la saturation par la file d'attente, le cache KV et le débit, pas par ce compteur.
2. Decode = mémoire (`DRAM_ACTIVE` haut) ; prefill long = calcul, et il **ralentit tout le monde** (TPOT x10 observé).
3. Un T4 en charge est au plafond de puissance (68/70 W) : l'horloge baisse. Ne pas attendre de miracle du réglage logiciel.

## 6. Exercice (à faire vous-même)

Objectif : diagnostiquer un goulot **sans** que je vous dise lequel. Lancez `./lab.sh bench steady` à un débit de votre choix, puis ouvrez le dashboard
« 02 - GPU » et dites, avec trois compteurs au plus : (1) le GPU est-il saturé ? (2) limité par le calcul ou par la mémoire ? (3) le CPU limite-t-il ?
Vérification : si `requests_waiting` reste à 0, la réponse à (1) est non, **même si `GPU_UTIL` vaut 100 %**.
