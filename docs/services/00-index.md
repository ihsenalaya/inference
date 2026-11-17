# Fiches par service

**En une phrase.** une fiche par composant du cluster, pour comprendre **ce qu'il fait**, **à qui il parle** et **quoi surveiller**.

<!-- mots: pod, namespace, argo cd, kserve, prometheus -->
> **Mots à connaître**
> - **Pod** : La plus petite unité qui tourne : un ou plusieurs conteneurs. Un pod vLLM = un modèle sur un GPU.
> - **Namespace** : Un « dossier » qui range les objets (`inference`, `gateway`, `monitoring`...).
> - **Argo CD / Application** : Applique ce qui est dans Git sur le cluster. Une *Application* = un composant suivi.
> - **KServe / `LLMInferenceService`** : Un seul objet déclare un modèle ; KServe crée les pods, le routage et le choix du pod.
> - **Prometheus / Alertmanager** : Stocke les métriques / envoie les alertes.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

Chaque fiche suit le même plan : **rôle**, **place dans l'architecture**, **relations**, **configuration retenue**, **authentification**, **données traitées**, **contribution à l'inférence**, **métriques à suivre**, **pannes et diagnostic**.
Convention de fiabilité (observé / config / doc / calcul / non vérifié) : voir [le guide](../guide/README.md).

Les fiches sont écrites pour un débutant : chacune commence par « En une phrase » et une boîte « Mots à connaître » ; [le glossaire](../sre/GLOSSAIRE.md) donne tous les mots.

Inventaire réel des workloads (images, requests, limites, ports, ServiceAccounts) : [docs/reference/workloads.txt](../reference/workloads.txt).

## Chemin de données (inférence)

| Service | Fiche | En une ligne |
|---|---|---|
| LiteLLM | [litellm.md](litellm.md) | passerelle d'API : clés virtuelles, budgets, quotas, routage par modèle |
| PostgreSQL | [postgres.md](postgres.md) | base de LiteLLM (clés, équipes, dépenses) |
| Gateway Istio | [istio.md](istio.md) | Envoy en tête de pool, appelle l'EPP |
| Gateway API + GIE (CRDs) | [gateway-api-et-gie.md](gateway-api-et-gie.md) | le vocabulaire (Gateway, HTTPRoute, InferencePool) |
| EPP llm-d | [llm-d-epp.md](llm-d-epp.md) | choisit le pod vLLM selon charge et cache de préfixes |
| vLLM | [vllm.md](vllm.md) | le moteur d'inférence |
| storage-initializer + Hugging Face | [storage-initializer.md](storage-initializer.md) | télécharge le modèle avant vLLM |

## Plan de contrôle

| Service | Fiche | En une ligne |
|---|---|---|
| KServe | [kserve.md](kserve.md) | transforme un `LLMInferenceService` en Deployment, EPP, route, pool |
| GPU Operator (+ driver, toolkit, device plugin, DCGM, NFD) | [gpu-operator.md](gpu-operator.md) | rend le GPU utilisable par Kubernetes |
| KEDA | [keda.md](keda.md) | ajuste le nombre de pods vLLM |
| LeaderWorkerSet | [lws.md](lws.md) | dépendance de KServe (inutilisé) |
| cert-manager | [cert-manager.md](cert-manager.md) | certificats du webhook KServe |
| Argo CD | [argocd.md](argocd.md) | applique Git sur le cluster |
| Pré-tirage d'image | [image-prepull.md](image-prepull.md) | tire l'image vLLM tôt (prouvé le 17/11 : pull de 1 s au lieu de 215 s) |

## Observabilité

| Service | Fiche | En une ligne |
|---|---|---|
| Prometheus (+ opérateur, kube-state-metrics, node-exporter) | [prometheus.md](prometheus.md) | métriques |
| Alertmanager (+ alert-sink) | [alertmanager.md](alertmanager.md) | routage des alertes |
| Grafana | [grafana.md](grafana.md) | dashboards |
| Loki | [loki.md](loki.md) | stockage des logs |
| Alloy | [alloy.md](alloy.md) | collecte des logs et événements |

## Plateforme et outillage

| Élément | Fiche | En une ligne |
|---|---|---|
| AKS et ressources Azure | [aks.md](aks.md) | cluster, pools, réseau, add-ons |
| Terraform | [terraform.md](terraform.md) | crée l'infrastructure et amorce Argo CD |
| inference-perf (banc de charge) | [bench.md](bench.md) | génère la charge et mesure |
