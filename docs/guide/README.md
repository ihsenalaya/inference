# Guide technique du cluster d'inférence

Ce guide explique **comment fonctionne l'inférence LLM** (faire répondre un modèle de langage) et **comment ce cluster la réalise**, service par service.
Il s'appuie sur ce qui a réellement tourné sur AKS (16 et 17/11/2026), pas sur une architecture théorique. Il est écrit pour quelqu'un qui **découvre** le sujet :
chaque chapitre commence par une petite boîte « Mots à connaître », et [le glossaire](../sre/GLOSSAIRE.md) réunit tous les mots en une ligne chacun.

## Par où commencer si vous débutez

1. Lisez les **12 premiers mots** du [glossaire](../sre/GLOSSAIRE.md) (5 minutes).
2. Lisez [le lab en une phrase](#le-lab-en-une-phrase) ci-dessous, puis [01 - L'inférence expliquée](01-inference-expliquee.md).
3. Passez à [02 - Architecture](02-architecture.md) pour suivre le trajet d'une requête.
4. Ensuite, au choix : la [formation](../formation/README.md) (mesurer, SLO, lire un GPU, démarrage à froid) ou les [fiches par service](../services/00-index.md).

## Convention de fiabilité

Chaque affirmation est rattachée à une source, pour que vous sachiez quoi croire :

| Marque | Signification |
|---|---|
| **(observé)** | constaté sur le cluster (commande, log, métrique, résultat de bench). Les extraits sont dans `docs/reference/` ou `results/`. |
| **(config)** | écrit dans le dépôt (fichier cité). C'est ce qui est déployé par Argo CD / Terraform. |
| **(doc)** | issu de la documentation officielle du composant, consultée pendant la construction (liens dans les fiches). |
| **(calcul)** | déduit d'un calcul dont les hypothèses sont écrites. Un ordre de grandeur, pas une mesure. |
| **(non vérifié)** | plausible mais non confirmé : à vérifier avant de s'en servir. |

## Ordre de lecture des chapitres

1. [01 - L'inférence expliquée](01-inference-expliquee.md) : tokens, prefill, decode, cache KV, batching, quantization, avec les chiffres du lab.
2. [02 - Architecture du cluster](02-architecture.md) : le chemin d'une requête, les plans de contrôle, le démarrage, les ports.
3. [03 - Identités et sécurité](03-identites-et-securite.md) : qui s'authentifie auprès de qui, comment, avec quoi.
4. [04 - Observabilité](04-observabilite.md) : quoi regarder, où, et comment lire les dashboards et les alertes.
5. [05 - Le GPU T4](05-gpu-t4.md) : ce que le matériel permet et interdit, et comment le lire.
6. [06 - Cycle de vie et coûts](06-cycle-de-vie-et-couts.md) : démarrage à froid, arrêt, destruction, coût.
7. Les fiches par service : [docs/services/](../services/00-index.md).

Documents complémentaires : [santé et efficacité du GPU](../gpu/README.md), [formation avec les vrais chiffres](../formation/README.md), [SLO par classe de charge](../sre/SLO.md), [compte rendu des séances](../sre/SEANCES.md), [BASELINE](../BASELINE.md) (mesures),
[DECISIONS](../DECISIONS.md) (pourquoi ces choix), [METRIQUES](../METRIQUES.md) (183 métriques réelles), [RUNBOOK](../RUNBOOK.md) (exploitation), [runbooks d'alertes](../runbooks/).

## Le lab en une phrase

Un client envoie une requête OpenAI-compatible à **LiteLLM** (la passerelle : clés, budgets), qui la transmet à une **Gateway Istio** (le routeur HTTP) ; un **EPP llm-d** (le sélecteur de pod) choisit le pod
**vLLM** (le moteur) le moins mal placé (charge, cache de préfixes) ; vLLM génère les tokens sur un **GPU T4** installé et exposé par le **GPU Operator** ;
**KServe** déclare l'ensemble, **KEDA** ajuste le nombre de pods, **Argo CD** applique tout depuis Git, et **Prometheus / Grafana / Loki / Alertmanager** observent.
