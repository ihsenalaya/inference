# Grafana Alloy

**En une phrase.** Alloy est le facteur des logs : il lit ce que chaque pod écrit et le dépose dans Loki.

<!-- mots: alloy, loki, daemonset, taint, serviceaccount -->
> **Mots à connaître**
> - **Grafana / Loki / Alloy** : Tableaux de bord / stockage des logs / agent qui collecte les logs.
> - **Deployment / DaemonSet / Job** : Programme à N copies / une copie par nœud / tâche qui se termine (un bench).
> - **Taint / toleration** : « Chasse-pods » posé sur le nœud GPU (`sku=gpu`) / autorisation pour les pods qui doivent y aller.
> - **ServiceAccount / jeton** : L'identité d'un programme dans Kubernetes et le « badge » temporaire qu'il présente à l'API.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Rôle
**Collecteur de logs** (et d'événements) : lit les logs des conteneurs via l'API Kubernetes et les pousse dans Loki. Version v1.22.0 (chart `grafana/alloy` 1.16.0), DaemonSet `alloy`.

## Place dans l'architecture
Un pod par nœud, **y compris le nœud GPU** (toleration `Operator: Exists` du taint). Namespace `monitoring`.

## Configuration retenue (config : `gitops/observability/alloy/values.yaml`)
- `discovery.kubernetes` filtré sur le **nœud local** (`spec.nodeName=$NODE_NAME`), `loki.source.kubernetes` (logs par l'API Kubernetes, sans hostPath), étiquettes : `namespace`, `pod`, `container`, `app`, `model` (`app.kubernetes.io/name`).
- `loki.source.kubernetes_events` pour les **événements Kubernetes**, avec **clustering** activé pour qu'un seul pod les collecte.
- Sortie : `http://loki.monitoring.svc:3100/loki/api/v1/push`.
- Ressources : 30 m / 96 Mi. ServiceMonitor activé.

## Authentification
ServiceAccount `alloy`, `ClusterRole alloy` : lecture des pods, `pods/log`, événements, **configmaps et secrets** (lecture cluster-wide : droit large livré par la chart, observé). Vers Loki : aucune.

## Données traitées
**Toutes les lignes de logs** de tous les conteneurs de tous les namespaces, plus les événements.

## Contribution à l'inférence
Rend les logs de vLLM, d'Envoy et de LiteLLM disponibles à côté des métriques, alignés dans le temps (dashboard 05).

## Métriques
`alloy_*`, `loki_source_kubernetes_*` ; vérification fonctionnelle : une requête LogQL sur `{namespace="inference"}` doit renvoyer des lignes.

## Pannes
Si l'API Kubernetes est lente, les logs arrivent en retard ; un pod sans droit `pods/log` n'est pas collecté ; le débit de logs d'un pod très bavard (vLLM) est limité par l'API server, pas par un fichier.
