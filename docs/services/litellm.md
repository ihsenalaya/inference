# LiteLLM - la passerelle d'API

**En une phrase.** LiteLLM est le guichet d'entrée : il vérifie la clé du client, applique ses limites, transmet la demande au modèle et compte ce qui est consommé.

<!-- mots: litellm, clé virtuelle, api compatible openai, streaming, classe de charge, secret -->
> **Mots à connaître**
> - **LiteLLM** : Passerelle OpenAI-compatible : clés virtuelles, budgets, limites, métriques par client.
> - **Clé virtuelle** : Clé d'API LiteLLM par client ; l'alias de la clé sert ici à identifier la **classe de charge**.
> - **API compatible OpenAI** : Une façon standard de parler à un LLM : `POST /v1/chat/completions`. Tous les composants du lab la parlent.
> - **Streaming** : La réponse arrive token par token au lieu d'un bloc à la fin.
> - **Classe de charge** : Un type d'usage avec son propre SLO : interactive, RAG, multi-tour, lot (embeddings non couverte).
> - **ConfigMap / Secret** : Configuration / données sensibles (mots de passe, clés) injectées dans les pods.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Rôle
Un **proxy compatible OpenAI** placé devant les modèles. Il apporte ce que vLLM ne fait pas : **clés virtuelles**, **équipes**, **budgets**, **limites** (requêtes/min, tokens/min), **routage par nom de modèle**, **fallbacks**, comptabilité de la dépense.
Version **v1.109.1**, image `ghcr.io/berriai/litellm` **épinglée par digest** (les versions PyPI 1.82.7 et 1.82.8 ont été compromises le 24/03/2026).

## Place dans l'architecture
Namespace `gateway`, Deployment `litellm` (1 réplica, pool système). C'est le **premier saut** : tout client (humain, application, banc de charge) parle à LiteLLM, jamais directement à la Gateway Istio.

## Relations
- **Client -> LiteLLM** : HTTP :4000, clé virtuelle en `Authorization: Bearer`.
- **LiteLLM -> PostgreSQL** : `DATABASE_URL` (clés, équipes, dépenses).
- **LiteLLM -> Gateway Istio** : `http://inference-gateway-istio.inference.svc.cluster.local/inference/<nom>/v1` (fournisseur `hosted_vllm/`).
- **Prometheus -> LiteLLM** : port dédié `:9400`, chemin `/metrics/`.

## Configuration retenue (config : `gitops/gateway/litellm`)
- **`model_list` généré par scénario** (`configmap.yaml`) à partir de `gitops/scenarios/<nom>.yaml` : un alias (`qwen-7b-awq`) est traduit en `hosted_vllm/<modèle Hugging Face>` avec l'`api_base` de la Gateway, `api_key: none` (vLLM ne vérifie rien). Un changement de scénario redémarre LiteLLM (annotation `checksum/config`).
- `litellm_settings` : `callbacks: ["prometheus"]`, `drop_params: true` ; `fallbacks` seulement dans le scénario `multi-model`.
- `general_settings` : `master_key` et `database_url` lus dans les variables d'environnement (secret `litellm-secrets`).
- Lancement : `--config /etc/litellm/config.yaml --port 4000 --num_workers 1 --prometheus_metrics_port 9400`, `PROMETHEUS_MULTIPROC_DIR=/tmp/prom`.
- Ressources : requests 100 m / 768 Mi, **limite 2 Gio** (voir pannes). Probes `/health/liveliness` et `/health/readiness`.
- **Hook Argo CD PostSync** (`bootstrap-keys.yaml`) : après chaque synchro, un job (`alpine/k8s`) crée, si le secret `litellm-keys` n'existe pas, **six** équipes avec leur clé : `lab-bench` (sans limite), `lab-user` (budget 5, 60 req/min, 20 000 tokens/min) et, depuis le 17/11, une par **classe de charge** SLO (`lab-interactive`, `lab-rag`, `lab-multiturn`, `lab-batch`, sans limite). L'alias de la clé permet de mesurer chaque classe séparément. Les clés sont rangées dans le secret `litellm-keys` ; le job est ignoré si ce secret existe déjà.

## Authentification
| Quoi | Mécanisme |
|---|---|
| Clients | **clé virtuelle** (`sk-...`), rattachée à une équipe ; vérifiée dans PostgreSQL |
| Administration | **master key** `LITELLM_MASTER_KEY` |
| Chiffrement des secrets stockés | `LITELLM_SALT_KEY` (ne jamais la changer après coup, doc LiteLLM) |
| Vers vLLM | aucune (`api_key: none`) |
| `/metrics` du port 4000 | exige une clé (observé) ; le port 9400 est ouvert au cluster |

## Données traitées
Le **contenu des requêtes et des réponses** (il lit et réécrit le JSON, gère le streaming SSE) et des **métadonnées de dépense** stockées dans PostgreSQL (clés, équipes, tokens, coût).
Que LiteLLM enregistre ou non les **prompts** en base dépend d'un réglage non activé dans notre configuration ; comportement par défaut non vérifié ici : à confirmer dans la doc v1.109 avant d'y envoyer des données sensibles.

## Contribution à l'inférence
- **Contrôle d'accès, quotas et attribution des coûts** par équipe.
- **Surcoût mesuré** : +50 ms au TTFT p50 sur le 7B à 1 req/s, +25 ms sur le 1,5B à 3 req/s (comparaison avec l'accès direct à la Gateway, `docs/BASELINE.md` §6).
- Le TPOT vu par le client est **plus faible** via LiteLLM qu'en direct (0,049 s contre 0,058 s à 1 req/s sur le 7B, observé) ; explication probable non vérifiée : regroupement des chunks SSE. Ne comparer le TPOT que sur le même chemin.
- **Mesure par classe** : les métriques `litellm_*` portent le label `api_key_alias` (= la classe) ; les SLO par classe s'appuient dessus ([SLO.md](../sre/SLO.md)). Limite constatée le 17/11 sur le lot 7B : le banc a compté 282 timeouts alors que LiteLLM n'a compté que 3 erreurs 500 sur 591 requêtes (explication non vérifiée) : un SLI côté passerelle ne voit pas ce que subit un client qui abandonne.
- Un **goulot possible** : 1 worker, ~1 Gio de mémoire au repos ; à 3-4 req/s (300+ flux concurrents lents) il a été **tué par OOM** à 1,25 Gio -> limite relevée à 2 Gio.

## Métriques à suivre (`litellm_*`, port 9400)
`litellm_proxy_total_requests_metric_total`, `litellm_proxy_failed_requests_metric_total`, `litellm_overhead_latency_metric`, `litellm_request_total_latency_metric`, `litellm_llm_api_latency_metric`, `litellm_in_flight_requests`, `litellm_spend_metric_total`, `litellm_remaining_team_budget_metric`, `litellm_deployment_state`.
Labels : `team`, `team_alias`, `api_key_alias`, `requested_model`, `model`, `api_provider`. Seaux des histogrammes de latence : 0,005 ... 1, 2, 5, 10, 30, 60, 120, 300, 420, 600 s (un seuil de SLO doit être l'un d'eux).

## Pannes et diagnostic
| Symptôme | Cause |
|---|---|
| `OOMKilled` (code 137) sous charge | limite mémoire trop basse (corrigée à 2 Gio) |
| clients : `Response payload is not completed`, connexions réinitialisées | redémarrage/OOM de LiteLLM pendant des flux |
| premier palier d'un bench en échec juste après un changement de scénario | LiteLLM redémarre (configuration changée) |
| `/metrics` renvoie 307 puis 401 | utiliser le port 9400 et le chemin `/metrics/` |
| clés absentes | le job `litellm-bootstrap-keys` n'a pas tourné : `kubectl -n gateway logs job/litellm-bootstrap-keys` |
