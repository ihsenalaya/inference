# vLLM - le moteur d'inférence

**En une phrase.** vLLM est le moteur : il charge le modèle sur le GPU et écrit la réponse token par token. Un pod vLLM = un modèle sur un GPU, et c'est le seul composant qui consomme le GPU.

<!-- mots: vllm, token, prefill, decode, cache kv, batching continu, vram -->
> **Mots à connaître**
> - **vLLM** : Le programme qui charge le modèle sur le GPU et répond aux requêtes. Le « moteur ».
> - **Token** : Le morceau de texte que le modèle lit et écrit (un mot courant fait environ 1 à 2 tokens). C'est l'unité de tous les calculs.
> - **Prefill** : Première phase : le modèle lit tout le prompt d'un coup. Plus le prompt est long, plus c'est long.
> - **Decode** : Deuxième phase : le modèle écrit la réponse token par token. Plus la réponse est longue, plus c'est long.
> - **Cache KV** : Mémoire où le modèle garde ce qu'il a déjà « compris » du texte, pour ne pas le refaire à chaque token. Il vit dans la mémoire du GPU.
> - **Batching continu** : vLLM traite ensemble les requêtes en cours, token par token ; une nouvelle requête rejoint le groupe sans attendre la fin des autres.
> - **GPU / VRAM** : Le processeur de calcul (ici un NVIDIA T4) et sa mémoire (16 Go). Le modèle et le cache KV doivent y tenir.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Rôle
Charge le modèle en mémoire GPU et **génère les tokens**. Il expose une API compatible OpenAI (`/v1/chat/completions`, `/v1/completions`, `/v1/models`...), un `/health` et un `/metrics` Prometheus.
Version **v0.32.0** (image officielle `vllm/vllm-openai`, épinglée par digest `sha256:befccf0e…`). Moteur « V1 » (log : `Initializing a V1 LLM engine (v0.32.0)`).

## Place dans l'architecture
Un pod par réplica, dans `inference`, sur le **nœud GPU** (1 T4 par pod, `nvidia.com/gpu: 1`). C'est le seul composant qui consomme le GPU. Créé par KServe (Deployment `<nom>-kserve`, conteneur `main`).

## Relations
- **Reçoit** de la Gateway (HTTP :8000) les requêtes dirigées par l'EPP.
- **Démarre après** le `storage-initializer` qui dépose le modèle dans `/mnt/models` (volume `kserve-provision-location`).
- **Scrapé par** : Prometheus (15 s) **et** l'EPP (qui lit ses métriques pour router).
- **Dépend de** : GPU Operator (driver, toolkit, device plugin) pour voir le GPU.

## Configuration retenue (config : `gitops/serving/chart`, `gitops/scenarios/*.yaml`)
Commande du preset KServe : `vllm serve /mnt/models --served-model-name <nom> ... --port 8000 --disable-access-log-for-endpoints /health,/metrics,/ping`. Nos arguments :

| Argument | Valeur | Pourquoi |
|---|---|---|
| `--dtype` | `float16` | le T4 n'a pas de bfloat16 |
| `--max-model-len` | `4096` | borne la longueur (prompt + sortie) ; conditionne le cache KV et la concurrence |
| `--gpu-memory-utilization` | `0.90` | part de la VRAM que vLLM peut utiliser (poids + KV + activations) |
| `--enable-prefix-caching` | oui | réutilise le KV des préfixes communs |
| (non modifiés) | `--max-num-seqs`, `--max-num-batched-tokens`, `-O` | valeurs par défaut de la v0.32.0 : leviers d'optimisation futurs |

Environnement : `HOME=/home`, `VLLM_LOGGING_LEVEL=INFO`, `HF_HUB_CACHE=/models`. Volumes : `/dev/shm` (1 Gio, mémoire), `/models`, `/tmp`, `/home` (emptyDir). Exécution en **uid 1000**, sans root.
Ressources : requests 2,5 CPU / 18 Gio ; **pas de limite CPU** ; limites 22 Gio et 1 GPU. Probes (tests de santé) : `startup` (jusqu'à 20 min), `readiness` (prêt à servir ?) et `liveness` (toujours vivant ?) sur `/health`.

Ce que vLLM a décidé lui-même sur ce T4 (**observé**, logs) :
- backend d'attention **`TRITON_ATTN`** (candidats : `TRITON_ATTN`, `FLEX_ATTENTION`) ; message `FA2 is only supported on devices with compute capability >= 8` (information, pas une panne) ;
- AWQ servi par **`MarlinLinearKernel`** ;
- poids en mémoire : 5,29 GiB (7B AWQ), chargement en 21,7 s ; `torch.compile` 19,8 s ; capture des graphes CUDA ~28 s ; **initialisation du moteur 72,8 s** ;
- cache KV : 6,97 GiB = **130 512 tokens** ; concurrence max annoncée à 4 096 tokens/requête : 31,86x. Au second déploiement du même 7B (17/11, mêmes réglages) vLLM a annoncé **113 760 tokens** : la mémoire disponible varie d'un démarrage à l'autre, **cause non élucidée**.

## Authentification
Aucune : le port 8000 accepte toute requête venant du cluster. La protection est en amont (LiteLLM). Le modèle est téléchargé **anonymement** depuis Hugging Face (par l'init container).

## Données traitées
Les **prompts et les tokens générés** en clair, en mémoire (et le cache KV, qui contient une représentation du contexte). Rien n'est écrit sur disque par vLLM dans notre configuration, hormis les caches de compilation (`/home/.cache/vllm`, `/tmp/vllm`, volumes éphémères). Les logs vLLM ne contiennent pas les prompts en niveau INFO (non vérifié ligne à ligne).

## Contribution à l'inférence
C'est l'inférence : prefill puis decode, batching continu, gestion du cache KV et du cache de préfixes. Performances mesurées sur 1 T4 (détail dans `docs/BASELINE.md`) :
- 7B AWQ : plateau ≈ 1,5-2 req/s (≈ 210-220 tokens/s de sortie) ; TTFT p50 0,63 s à 1 req/s ; **prompts longs : effondrement** (TTFT p50 102 s à 0,5 req/s de 2 000-3 500 tokens) à cause de l'attention Triton sans tensor cores.
- 1,5B FP16 : plateau ≈ 5 req/s (≈ 750 tokens/s) ; en lot saturé (7 req/s demandées) **933 tokens/s** observés le 17/11.
- Par classe de charge (SLO) : seule l'interactive tient son objectif sur les deux modèles ; détail dans [SLO.md](../sre/SLO.md).

## Métriques à suivre (observé, 70 familles `vllm:*`)
Essentielles : `num_requests_running`, `num_requests_waiting`, `kv_cache_usage_perc`, `num_preemptions_total`, `time_to_first_token_seconds`, `inter_token_latency_seconds`, `e2e_request_latency_seconds`, `request_queue_time_seconds`, `request_prefill_time_seconds`, `request_decode_time_seconds`, `prompt_tokens_total`, `generation_tokens_total`, `prefix_cache_hits_total` / `_queries_total`, `request_success_total`, `estimated_flops_per_gpu_total`.
Voir [guide observabilité §6](../guide/04-observabilite.md).

## Pannes et diagnostic
| Symptôme | Cause / réponse |
|---|---|
| Pod `Pending` | GPU non annoncé (driver en cours), ou aucun nœud T4 libre |
| `CreateContainerConfigError` | `runAsNonRoot` avec une image root |
| `no kernel image is available` (non rencontré) | image sans noyau sm_75 : c'est l'image `llm-d-cuda:v0.9.0` du preset, d'où le remplacement |
| Pod `Running 0/1` plusieurs minutes | chargement + compilation (≈ 2,5 min) |
| File qui grandit, TTFT qui explose | saturation de calcul : ajouter un réplica ou réduire la charge |
| Préemptions | cache KV insuffisant : `--max-model-len`, `--max-num-seqs`, quantization |
| Requêtes très lentes sur prompts longs | attention Triton sur Turing (issue vLLM #60821) |
