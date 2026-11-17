# 01 - L'inférence expliquée avec les chiffres du lab

Objectif : comprendre pourquoi les chiffres de `docs/BASELINE.md` sont ce qu'ils sont. Les chiffres viennent du lab (7B AWQ et 1,5B FP16 sur 1 T4) ;
les calculs sont marqués **(calcul)** avec leurs hypothèses.

**L'idée en 30 secondes.** Un modèle de langage écrit un peu comme quelqu'un qui, avant chaque mot, relit tout ce qui précède, avec un marque-page pour ne pas tout refaire (le *cache KV*).
Lire la consigne d'un coup, c'est le *prefill* ; écrire mot après mot, c'est le *decode*. Ce chapitre explique pourquoi ces deux phases ne coûtent pas la même chose, et ce que ça change pour la vitesse et la mémoire.
(L'image est une aide, pas une description exacte du calcul.)

<!-- mots: token, prefill, decode, cache KV, batching continu, ttft, tpot, vram -->
> **Mots à connaître**
> - **Token** : Le morceau de texte que le modèle lit et écrit (un mot courant fait environ 1 à 2 tokens). C'est l'unité de tous les calculs.
> - **Prefill** : Première phase : le modèle lit tout le prompt d'un coup. Plus le prompt est long, plus c'est long.
> - **Decode** : Deuxième phase : le modèle écrit la réponse token par token. Plus la réponse est longue, plus c'est long.
> - **Cache KV** : Mémoire où le modèle garde ce qu'il a déjà « compris » du texte, pour ne pas le refaire à chaque token. Il vit dans la mémoire du GPU.
> - **Batching continu** : vLLM traite ensemble les requêtes en cours, token par token ; une nouvelle requête rejoint le groupe sans attendre la fin des autres.
> - **TTFT** : *Time To First Token* : attente avant le premier token de la réponse. C'est ce que l'utilisateur ressent en premier.
> - **TPOT** : *Time Per Output Token* : durée moyenne entre deux tokens de la réponse. C'est la « fluidité » du texte qui s'affiche.
> - **GPU / VRAM** : Le processeur de calcul (ici un NVIDIA T4) et sa mémoire (16 Go). Le modèle et le cache KV doivent y tenir.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## 1. Ce que fait un LLM quand il « répond »

Un LLM ne produit pas une phrase : il produit **un token à la fois**. Un token est un morceau de mot (en moyenne un peu moins qu'un mot en français).
Pour chaque nouveau token, le modèle relit **tout le contexte précédent** (le prompt et ce qu'il a déjà généré) et calcule une distribution de probabilité sur le prochain token ;
un échantillonnage (paramètre `temperature`) en choisit un. On répète jusqu'à la fin ou jusqu'à `max_tokens`.

Une requête a donc **deux phases** qui n'ont pas le même coût :

| Phase | Ce qui se passe | Limitée par | Métrique client | Métrique vLLM |
|---|---|---|---|---|
| **Prefill** | le prompt entier est traité d'un coup, en parallèle ; on remplit le cache KV | **le calcul** (multiplications de matrices) | TTFT (temps jusqu'au 1er token) | `vllm:request_prefill_time_seconds`, `vllm:time_to_first_token_seconds` |
| **Decode** | un token à la fois ; chaque étape relit tous les poids du modèle | **la bande passante mémoire** (avec un petit batch) | TPOT / latence inter-token | `vllm:inter_token_latency_seconds`, `vllm:request_decode_time_seconds` |

Latence de bout en bout ≈ TTFT + (nombre de tokens générés - 1) x TPOT **(calcul)**.
Vérification sur le lab : 7B AWQ à 1 req/s via LiteLLM, sorties moyennes ~128 tokens, TPOT p50 = 0,049 s, TTFT p50 = 0,63 s
=> 0,63 + 127 x 0,049 = 6,9 s ; latence p50 mesurée = 7,55 s **(observé)** : même ordre de grandeur (les sorties les plus longues, jusqu'à 256 tokens, tirent la moyenne vers le haut).
Remarque : ce TPOT (0,049 s) vient d'un run de 3 minutes sans échauffement ; avec 60 s d'échauffement et 5 minutes, le TPOT p50 du 7B a été de 0,070 s ([module 1](../formation/01-mesurer-sans-se-tromper.md)). Les deux sont des mesures réelles : on ne compare que des runs faits avec le même protocole.

## 2. Le cache KV : la mémoire qui limite la concurrence

Pour ne pas recalculer le contexte à chaque token, vLLM garde les **clés et valeurs d'attention (K, V)** de chaque token déjà vu : le **cache KV**.
Il occupe de la VRAM et grossit avec le nombre de tokens en cours de traitement (toutes requêtes confondues).

Taille par token **(calcul)**, pour Qwen2.5-7B (28 couches, 4 têtes KV, dimension 128 par tête, FP16 ; paramètres du modèle : fiche Hugging Face) :

```
2 (K et V) x 28 couches x 4 têtes x 128 x 2 octets = 57 344 octets par token
```

vLLM a annoncé au démarrage : `Available KV cache memory: 6,97 GiB` et `GPU KV cache size: 130 512 tokens` **(observé)** :
130 512 x 57 344 octets = 7,48 x 10^9 octets = **6,97 GiB**. Le calcul retombe exactement sur la valeur mesurée : le modèle de mémoire est juste.

Conséquence : avec `--max-model-len 4096`, vLLM annonce `Maximum concurrency for 4 096 tokens per request: 31,86x` **(observé)** = 130 512 / 4 096.
Autrement dit le cache peut contenir ~32 requêtes de 4 096 tokens, ou beaucoup plus de requêtes plus courtes. Quand le cache est plein, vLLM met des requêtes en attente
ou en **préemption** (`vllm:num_preemptions_total`) : elles sont évincées puis recalculées, ce qui coûte de la latence.

Où va la VRAM d'un T4 (16 Go) avec `--gpu-memory-utilization 0.90` et le 7B AWQ **(observé, logs vLLM)** :

| Poste | Taille |
|---|---|
| Poids du modèle (AWQ 4 bits) | 5,29 GiB |
| Cache KV | 6,97 GiB |
| Activations de pointe (résultats intermédiaires du calcul, 1,45 GiB) + graphes CUDA (calculs GPU préenregistrés pour aller plus vite, 0,22 GiB) + mémoire hors PyTorch (~0,29 GiB) | ~1,96 GiB |
| **Total** | ~14,2 GiB (= 0,90 x 15,56 GiB de la carte, comme demandé) |

`nvidia-smi` affiche 14 447 MiB utilisés : vLLM **préalloue** presque toute la carte, utilisée ou non. Pour le 1,5B FP16, DCGM a relevé 14 860 MiB, bien que ses poids ne fassent qu'~3 Go
**(observé)** : la VRAM utilisée dépend du réglage `gpu-memory-utilization`, pas de la taille du modèle.

## 3. Le batching continu : pourquoi un GPU sert plusieurs requêtes à la fois

Lire 5,3 Gio de poids pour produire **un** token est peu efficace. vLLM regroupe donc, à chaque étape de decode, un token de **chaque requête en cours** : un **batch**.
Les poids ne sont lus qu'une fois pour tout le batch. Le batch change à chaque étape (une requête qui finit est remplacée par une nouvelle : *continuous batching*).

- `vllm:num_requests_running` = taille du batch courant ; `vllm:num_requests_waiting` = file d'attente (requêtes qui n'ont pas pu entrer).
- Les réglages qui bornent le batch sont `--max-num-seqs` (nombre de requêtes) et `--max-num-batched-tokens` (nombre de tokens par étape). **Nous ne les avons pas modifiés** (valeurs par défaut de vLLM v0.32.0) : ce sont des leviers de la campagne d'optimisation.

Borne théorique du decode à batch 1 **(calcul)** : lire 5,29 Gio (5,68 x 10^9 octets) à la bande passante d'un T4 (320 Go/s, fiche NVIDIA)
=> 17,7 ms par token. Mesuré à faible charge : TPOT p50 = 21,5 ms (smoke, via LiteLLM) **(observé)**. L'ordre de grandeur colle : au repos, le decode est limité par la mémoire.

## 4. Saturation : ce que montre le sweep

Le *sweep* (balayage : on augmente le débit par paliers) envoie une charge **à débit imposé** (boucle ouverte : les requêtes arrivent à la cadence demandée, même si le serveur est en retard) et mesure ce qui sort **(observé, BASELINE §5)** :

| req/s demandées | 7B AWQ : req/s servies | TTFT p50 | 1,5B FP16 : req/s servies | TTFT p50 |
|---|---|---|---|---|
| 1 | 0,94 | 0,68 s | - | - |
| 2 | 1,47 | 2,4 s | - | - |
| 3 | 1,54 | 19 s | - | - |
| 4 | (effondrement) | - | 3,50 | 0,39 s |
| 8 | - | - | 5,05 | 1,4 s |
| 12 | - | - | 5,17 | 23 s |

Lecture : au-dessus du **plateau** (≈ 1,5 req/s pour le 7B, ≈ 5 req/s pour le 1,5B), le serveur ne sert pas plus ; la file d'attente grandit et le TTFT explose.
C'est la loi de Little (ce qui est en cours = débit x durée de chaque requête). À 1 req/s et 7,5 s de latence, ~7,5 requêtes sont en vol ; si le débit demandé dépasse la capacité, la file ne se vide plus.
Pourquoi une **boucle ouverte** : avec une concurrence fixe (boucle fermée), le client ralentit quand le serveur ralentit et masque la file d'attente.

Qui est le goulot ? Pendant les sweeps : activité du moteur graphique 78-84 %, activité DRAM 16-22 %, CPU de vLLM <= 1,1 cœur sur 4 **(observé, Prometheus/DCGM)**.
Un moteur occupé et une mémoire peu sollicitée désignent le **calcul** comme limite, pas la bande passante ni le CPU.

## 5. Le prefill sur T4 : un problème matériel et logiciel

Le prefill coûte ~2 x (nombre de paramètres) FLOP (opérations de calcul) par token de prompt **(calcul)** : pour 7,6 milliards de paramètres, ~15 GFLOP (milliards d'opérations) par token.
Sur le profil `long-prompt` (prompts 2 000 à 3 500 tokens), le débit de prompt traité était ~370 tokens/s => ~5,6 TFLOP/s effectifs **(calcul à partir de l'observé)**.
Les tensor cores (unités du GPU spécialisées en multiplication de matrices) d'un T4 offrent jusqu'à 65 TFLOP/s (65 000 milliards d'opérations par seconde) en FP16 (fiche NVIDIA) : on en utilise moins de 10 %.

La cause connue : sur compute capability 7.5 (la « génération » du T4), vLLM v0.32.0 sélectionne `TRITON_ATTN` (l'implémentation du calcul d'attention écrite avec Triton) (logs : `Using TRITON_ATTN attention backend out of potential backends: ['TRITON_ATTN', 'FLEX_ATTENTION']`) **(observé)**,
et depuis Triton 3.3 ces noyaux n'utilisent plus les tensor cores sur Turing (issue vLLM #60821, **doc**). La correction (PR #55380) n'est pas fusionnée.
Effet mesuré : TTFT p50 = **102 s** sur `long-prompt` en 7B, contre 2,8 s pour le 1,5B qui a ~5x moins de calcul à faire **(observé)**.

Mise à jour (17/11, compteurs DCGM lus sur un second cluster) : les tensor cores **ne sont pas inactifs** (`PIPE_TENSOR_ACTIVE` de 0,28 à 0,32 avec le 7B AWQ, 0,04 à 0,14 avec le 1,5B ; **observé**). Ce sont probablement les multiplications de matrices
qui les utilisent, le noyau d'attention Triton étant celui qui n'en profite pas : **hypothèse non vérifiée**. Voir le [module 5 de la formation](../formation/05-lire-un-gpu.md).

## 6. Le cache de préfixes : ne pas recalculer ce qui est identique

Si deux requêtes commencent par le même texte (prompt système, document), vLLM réutilise le cache KV déjà calculé (`--enable-prefix-caching`, activé dans nos scénarios).
Sur le profil `shared-prefix` (4 préfixes de 1 024 tokens partagés par 16 utilisateurs) **(observé)** :

| | steady (prompts sans préfixe commun) | shared-prefix |
|---|---|---|
| TTFT p50, 7B, 1 req/s | 0,63 s | 0,14 s |
| taux de hit du cache de préfixes | - | 98-99 % |

Le préfixe de 1 024 tokens n'est calculé qu'une fois ; ensuite seul le reste du prompt passe par le prefill. C'est aussi la raison d'être de l'EPP (fiche llm-d) :
envoyer les requêtes qui partagent un préfixe au pod qui l'a déjà en cache.

## 7. La quantization : changer de compromis mémoire / calcul

Le 7B en FP16 pèserait ~15 Go (7,6 x 10^9 x 2 octets, **calcul**) : il ne tiendrait pas avec un cache KV dans 16 Go. En **AWQ 4 bits** il pèse 5,29 Gio **(observé)**.
Sur Turing (l'architecture du T4), vLLM utilise le noyau Marlin (un petit programme GPU optimisé pour les poids 4 bits) pour AWQ (`Using MarlinLinearKernel for AutoAWQMarlinLinearMethod`, **observé**). Le T4 ne sait pas faire de bfloat16 ni de FP8 : on impose `--dtype float16`.
Le gain principal d'AWQ ici est la **mémoire** (plus de place pour le KV), pas la vitesse de calcul : à mesurer (expérience M1 du plan de campagne).

## 8. Vocabulaire des métriques de latence

| Terme | Définition | Où le lire |
|---|---|---|
| TTFT | délai entre l'envoi et le 1er token reçu | bench (`time_to_first_token`), vLLM (`vllm:time_to_first_token_seconds`), dashboard 00 |
| TPOT | temps moyen par token de sortie d'une requête | bench |
| ITL (inter-token latency) | délai entre deux tokens consécutifs | vLLM (`vllm:inter_token_latency_seconds`) |
| Latence de bout en bout | durée totale de la requête | `vllm:e2e_request_latency_seconds` |
| Goodput | débit des requêtes qui respectent le SLO | défini par classe de charge dans [SLO.md](../sre/SLO.md) ; calculé par `tests/goodput.py` |
| Débit brut | tokens de sortie par seconde, toutes requêtes | `lab:generation_tokens:rate1m` |

Piège de mesure déjà rencontré **(observé)** : via LiteLLM, le TPOT client est plus bas que via la Gateway directe (0,049 s contre 0,058 s à 1 req/s sur le 7B).
Explication probable (**non vérifiée**) : LiteLLM regroupe ou re-cadence les morceaux du flux de streaming (les « chunks SSE », format d'événements HTTP), ce qui lisse les intervalles vus par le client. Comparer le TPOT **entre deux runs du même chemin**, jamais entre deux chemins.
