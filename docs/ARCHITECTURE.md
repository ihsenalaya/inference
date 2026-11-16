# Architecture

## Chemin d'une requête

`client -> LiteLLM -> Gateway Istio -> HTTPRoute -> InferencePool + EPP llm-d -> pod vLLM (1 T4)`

- **LiteLLM** (AI gateway) : clés virtuelles, budgets, quotas, routage par modèle (`model_list` généré par scénario), fallback.
  PostgreSQL stocke clés, équipes, dépenses. Deux équipes créées par un hook Argo CD PostSync : `lab-bench` (sans limite), `lab-user`
  (budget 5, 60 rpm, 20 000 tpm).
- **Gateway Istio** : `Gateway` Gateway API de classe `istio`, Service ClusterIP, pas de sidecar dans les namespaces d'inférence.
  Istio upstream (chart `istiod` seul) avec `ENABLE_GATEWAY_API_INFERENCE_EXTENSION=true`.
- **EPP llm-d** (Endpoint Picker) : appelé en `ext_proc` gRPC par Envoy ; choisit le pod selon le cache de préfixes, la file et la charge.
  Il sert en TLS auto-signé : une `DestinationRule` (`insecureSkipVerify`) est nécessaire sinon HTTP 500.
- **KServe `LLMInferenceService`** (v1alpha2) : déclare workload vLLM, route, InferencePool, scheduler, et le `ScaledObject` KEDA.
- **vLLM** : image officielle `vllm/vllm-openai` (la livrée par KServe n'a pas de noyau sm_75, cf. D-03).

## Deux chemins de test

`lab.sh bench ... --target litellm` (chaîne complète) et `--target gateway` (directement la Gateway). L'écart mesure le surcoût de LiteLLM.

## Infrastructure (Terraform)

- AKS tier Free, identité managée, OIDC et workload identity, Azure CNI Overlay, aucun add-on Azure Monitor/Istio/KAITO,
  pas de mise à jour automatique (une nouvelle image de nœud change le noyau et relance le build du driver).
- Pool système `Standard_D4as_v7` (1 nœud) : toute la plateforme. Pool GPU `Standard_NC4as_T4_v3` : `gpu_driver = "None"`
  (le GPU Operator installe le driver), taint `sku=gpu:NoSchedule`, disque OS éphémère 128 Gio.
- Terraform installe Argo CD (`helm_release`), crée les secrets et l'application racine ; ensuite tout vit dans Git.

## GitOps

Application racine -> chart `gitops/root` -> une Application par composant, ordonnées par vagues :

| Vague | Contenu |
|---|---|
| 0 | CRDs Gateway API v1.5.1 et GIE v1.5.0 |
| 1 | cert-manager, kube-prometheus-stack |
| 2-3 | istio-base ; istiod, GPU Operator, KEDA, LeaderWorkerSet, Loki, Alloy |
| 4-6 | KServe (CRDs, contrôleur, presets), Gateway |
| 7-8 | scénario de serving, PostgreSQL, LiteLLM |
| 9 | ServiceMonitors, règles, dashboards |

Les applications convergent par réessais (backoff) : l'ordre est une aide, pas une garantie (constaté sur kind).

## Observabilité

Prometheus (rétention 7 j), règles d'enregistrement `lab:*`, alertes avec `runbook_url` (docs/runbooks), Grafana provisionné
(6 dashboards maison, 5 dashboards llm-d, DCGM), Loki (logs pods + événements), Alertmanager (inhibition, webhook ou récepteur local).
