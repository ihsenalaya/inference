# Module 2 - Classes de charge et SLI : pourquoi un SLO global ne veut rien dire en inférence

**Objectif** : savoir définir des **classes de charge**, choisir les bons **SLI** pour chacune, et savoir **où** chaque SLI se mesure dans ce cluster
(client, passerelle, moteur). Marques de fiabilité : voir [le guide](../guide/README.md).

## 1. Le concept en dix lignes

1. Une requête d'inférence n'a pas de « coût » unique. Son temps de calcul dépend de la **longueur du prompt** (prefill, calcul) et de la **longueur de la réponse** (decode, mémoire).
2. Mélanger un prompt de 2 750 tokens et un prompt de 300 tokens dans un seul SLO donne une moyenne qui ne décrit personne. **Un SLO par classe**, jamais un SLO global.
3. Chaque classe a ce qui compte pour son utilisateur : le **chat** attend le premier token (TTFT) puis un flux régulier (temps par token) ; un **traitement de lot**
   n'a personne qui attend, seul compte le débit.
4. Les classes se **gênent** : un prefill long retarde les tokens de tous les autres (module 5 : TPOT x10 observé). C'est la raison d'être de classes séparées, avec leur propre mesure.

## 2. Les classes du lab et leur profil de charge (config)

| Classe | Forme | Profil `gitops/bench/profiles/` | Clé virtuelle LiteLLM (alias) | Ce qui compte |
|---|---|---|---|---|
| **Interactive** | chat en streaming, prompts courts (64-512 tokens), réponses de 32-256 | `interactive` | `lab-interactive` | TTFT, temps par token |
| **RAG** | prompt long (2 000-3 500 tokens), réponse courte (16-64) | `long-prompt` | `lab-rag` | TTFT (prefill) |
| **Multi-tour** | conversation, préfixe qui grandit (16 sessions, système de 256 tokens) | `multi-turn` | `lab-multiturn` | TTFT, cache de préfixes |
| **Lot** | gros volume sans utilisateur en attente (512 -> 256 tokens) | `batch` | `lab-batch` | débit (tokens/s), coût |
| **Embeddings** | requêtes courtes, très nombreuses | **aucun** | **aucune** | **non mesurée : le lab ne déploie aucun modèle d'embeddings** |

L'identification se fait **par la clé virtuelle** : un client = une classe = une clé. LiteLLM met l'alias de la clé (`api_key_alias`) et l'équipe (`team_alias`) comme labels sur
ses métriques (**observé** : `litellm_llm_api_time_to_first_token_metric`, `litellm_request_total_latency_metric`, `litellm_proxy_total_requests_metric_total`). C'est le seul moyen, dans ce
lab, d'avoir un SLI **par classe** côté serveur : vLLM, lui, ne sait pas qui est qui.

## 3. Les SLI et où on les mesure

| SLI | Définition | Client (banc) | Passerelle (LiteLLM, par classe) | Moteur (vLLM, global) |
|---|---|---|---|---|
| **TTFT** | délai entre l'envoi et le premier token | `requests.csv` (`ttft`) | `litellm_llm_api_time_to_first_token_metric` | `vllm:time_to_first_token_seconds` |
| **Temps par token (TPOT)** | durée moyenne entre deux tokens de sortie | `requests.csv` (`tpot`) | `litellm_deployment_latency_per_output_token` | `vllm:inter_token_latency_seconds` |
| **Latence de bout en bout** | envoi -> dernier token | `requests.csv` (`end - start`) | `litellm_request_total_latency_metric` | `vllm:e2e_request_latency_seconds` |
| **Taux de succès** | requêtes sans échec 5xx / 408 | `error` | `litellm_proxy_failed_requests_metric_total` / total | `vllm:request_success_total` |
| **Goodput** | requêtes **par seconde** qui respectent le SLO | `tests/goodput.py` | `rate(bucket{le=seuil})` | non disponible par classe |

Deux pièges propres à ce lab (**observé**) :

1. **Les quantiles de l'histogramme sont grossiers.** Pour la classe interactive du 1,5B, le **client** mesure une latence de bout en bout p95 de **5,66 s** ; LiteLLM et vLLM, qui
   calculent leur p95 avec `histogram_quantile` sur des seaux `5 s` et `10 s`, annoncent **8,9 s**. Ce n'est pas un écart réel : le vrai p95 est dans le seau (5 s, 10 s] et l'interpolation
   linéaire le place trop haut. **Ne comparez pas un p95 client à un p95 d'histogramme sans regarder les seaux.** Pour un SLO, on évite l'interpolation : on compte les requêtes sous un seuil qui est
   **exactement** un seau.
2. **Le client et le serveur ne comptent pas les mêmes requêtes.** Le banc ne retient que les requêtes dont l'envoi tombe dans la fenêtre de mesure ; le serveur compte celles qui **se
   terminent** dans la fenêtre. Quand une file se forme (classe lot), l'écart est énorme (voir §5).

## 4. Définition d'une requête « bonne » (config)

Elle est **identique** côté client et côté règles Prometheus, et **écrite à un seul endroit** : `slo.classes` dans `gitops/observability/config/values.yaml`
(lu par `tests/goodput.py` et par le chart des règles).

- Disponibilité : pas d'échec 5xx ni 408. Les **4xx** (faute du client) ne comptent pas côté serveur.
- TTFT <= seuil de la classe, et durée de bout en bout <= seuil de la classe (quand la classe les définit).
- Goodput = nombre de requêtes bonnes / durée de la fenêtre.

Les valeurs des seuils et leur justification : [docs/sre/SLO.md](../sre/SLO.md).

## 5. Résultats mesurés par classe

Les tableaux complets (1,5B et 7B) sont dans [docs/sre/SLO.md](../sre/SLO.md), section « Mesures par classe ». Pour le 1,5B FP16 (1 T4, 300 s de mesure après 60 s d'échauffement) :

| Classe | Débit demandé | Requêtes | Part bonne | Goodput (req/s) | TTFT p50 / p95 | TPOT p50 | Durée p95 (client) |
|---|---|---|---|---|---|---|---|
| Interactive | 2 req/s | 600 | **100 %** | 2,00 | 0,12 / 0,20 s | 0,020 s | 5,7 s |
| RAG | 0,5 req/s | 150 | **91,3 %** (SLO 95 % : **non respecté**) | 0,46 | 3,1 / 8,8 s | **0,20 s** | 30,0 s |
| Multi-tour | 0,5 req/s | 150 | **96,0 %** (6 échecs) | 0,48 | 0,44 / 0,81 s | 0,024 s | 6,4 s |
| Lot | 7 req/s (au-dessus de la capacité) | 1 112 | 100 % | 3,71 | **39 / 43 s** | 0,27 s | **146 s** |

Lecture :
- Le **RAG** sur le 1,5B respecte presque son SLO mais pas à 95 % : 13 requêtes sur 150 ont dépassé 10 s de TTFT ou 30 s de durée. Son TPOT est **10x** celui de l'interactif.
- Le **lot** sature le GPU (933 tokens/s, trois fois le débit interactif) et accepte une latence énorme : TTFT p50 39 s, durée p95 146 s, tout en restant dans son SLO de 300 s. C'est exactement
  pour cela qu'on ne lui applique pas le SLO d'une classe interactive.
- Le **multi-tour** : un premier essai à 2 req/s a produit **76 % d'erreurs 400** (`ContextWindowExceededError`, contexte > 4 096 tokens) : les 16 conversations simulées grossissent à chaque
  tour sans jamais être tronquées, et dépassent `max-model-len`. C'est un comportement du **générateur** (une vraie application tronque ou résume l'historique), pas une panne du cluster ;
  il illustre néanmoins que **le contexte maximal est une limite dure d'une classe multi-tour**. L'essai a été refait à 0,5 req/s, où les conversations restent sous la limite.
  (Run conservé : `results/2026-11-17-small-fp16-multi-turn-class-2rps-context-overflow`.)

## 6. À retenir

1. Un SLO par classe, avec le SLI qui compte pour elle : TTFT pour le RAG, TTFT et temps par token pour le chat, débit pour le lot.
2. Un client = une clé = une classe : c'est ce qui permet une mesure **par classe** côté serveur.
3. Un seuil de SLO sur un histogramme doit être **un seau** ; un p95 d'histogramme n'est pas comparable à un p95 client.

## 7. Exercice (à faire vous-même)

Objectif : ajouter la classe **« embeddings »** sans rien me demander.
1. Quel modèle déployer, et sur quel GPU (le T4 est déjà pris par le modèle de chat) ? Qu'est-ce que cela change pour `gpu-sharing` et pour le coût ?
2. Quels SLI et quel profil de charge (entrées courtes, sorties vectorielles, pas de streaming) ?
3. Comment la clé `lab-embeddings` s'ajoute-t-elle sans geste manuel (indice : la boucle des classes dans `gitops/gateway/litellm/templates/bootstrap-keys.yaml`) ?
Vérification : la classe apparaît dans `slo.classes` (règles et alertes générées automatiquement), la clé existe après un redéploiement sans geste manuel, et vous avez ajouté son panneau
dans `tests/gen_dashboards.py` (le dashboard « 06 » n'est **pas** généré depuis `slo.classes` : limite connue).
