# Guide technique du cluster d'inférence

Ce guide explique **comment fonctionne l'inférence LLM** et **comment ce cluster la réalise**, service par service.
Il s'appuie sur ce qui a réellement tourné sur AKS (16-17/11/2026), pas sur une architecture théorique.

## Convention de fiabilité

Chaque affirmation est rattachée à une source, pour que vous sachiez quoi croire :

| Marque | Signification |
|---|---|
| **(observé)** | constaté sur le cluster (commande, log, métrique, résultat de bench). Les extraits sont dans `docs/reference/` ou `results/`. |
| **(config)** | écrit dans le dépôt (fichier cité). C'est ce qui est déployé par Argo CD / Terraform. |
| **(doc)** | issu de la documentation officielle du composant, consultée pendant la construction (liens dans les fiches). |
| **(calcul)** | déduit d'un calcul dont les hypothèses sont écrites. Un ordre de grandeur, pas une mesure. |
| **(non vérifié)** | plausible mais non confirmé : à vérifier avant de s'en servir. |

## Ordre de lecture conseillé

1. [01 - L'inférence expliquée](01-inference-expliquee.md) : tokens, prefill, decode, cache KV, batching, quantization, avec les chiffres du lab.
2. [02 - Architecture du cluster](02-architecture.md) : le chemin d'une requête, les plans de contrôle, le démarrage, les ports.
3. [03 - Identités et sécurité](03-identites-et-securite.md) : qui s'authentifie auprès de qui, comment, avec quoi.
4. [04 - Observabilité](04-observabilite.md) : quoi regarder, où, et comment lire les dashboards et les alertes.
5. [05 - Le GPU T4](05-gpu-t4.md) : ce que le matériel permet et interdit, et comment le lire.
6. [06 - Cycle de vie et coûts](06-cycle-de-vie-et-couts.md) : démarrage à froid, arrêt, destruction, coût.
7. Les fiches par service : [docs/services/](../services/00-index.md).

Documents complémentaires : [BASELINE](../BASELINE.md) (mesures), [DECISIONS](../DECISIONS.md) (pourquoi ces choix),
[METRIQUES](../METRIQUES.md) (183 métriques réelles), [RUNBOOK](../RUNBOOK.md) (exploitation), [runbooks d'alertes](../runbooks/).

## Le lab en une phrase

Un client envoie une requête OpenAI-compatible à **LiteLLM**, qui la transmet à une **Gateway Istio** ; un **EPP llm-d** choisit le pod
**vLLM** le moins mal placé (charge, cache de préfixes) ; vLLM génère les tokens sur un **GPU T4** installé et exposé par le **GPU Operator** ;
**KServe** déclare l'ensemble, **KEDA** ajuste le nombre de pods, **Argo CD** applique tout depuis Git, et **Prometheus / Grafana / Loki / Alertmanager** observent.
