# Argo CD

## Rôle
**Contrôleur GitOps** : il compare en continu l'état du cluster à ce qui est décrit dans le dépôt Git et **corrige l'écart**. C'est lui qui installe tous les composants (hors infrastructure Azure et amorçage).

## Place dans l'architecture
Installé par Terraform (namespace `argocd`). Il reçoit **une seule** Application racine ; celle-ci en génère **19** (une par composant, `gitops/root/templates/apps.yaml`). Argo CD est donc le « chef d'orchestre » du plan de contrôle.

Workloads observés (v3.6.1) : `argocd-application-controller` (StatefulSet, réconcilie), `argocd-repo-server` (clone le dépôt, rend Helm/Kustomize), `argocd-server` (API et UI), `argocd-redis` (cache), `argocd-applicationset-controller`.

## Relations
- **Amont** : GitHub `ihsenalaya/inference` (branche `main`), en HTTPS anonyme (dépôt public).
- **Aval** : l'API Kubernetes (applique les manifestes), et les registres Helm (jetstack, istio, nvidia, kedacore, prometheus-community, grafana, ghcr.io/kserve, registry.k8s.io) pour les charts amont.

## Configuration retenue (config : `gitops/bootstrap/argocd-values.yaml`, `gitops/root/templates/apps.yaml`)
- **App-of-apps** : l'Application racine pointe sur le chart `gitops/root` avec les paramètres `env`, `gpuNodes`, `disable`... et le fichier `gitops/active-<env>.yaml` (scénario actif).
- **Multi-sources** : pour un chart tiers, source 1 = le chart (version exacte, `versions.yaml`), source 2 = ce dépôt (`ref: values`) qui fournit `values.yaml` et `values-<env>.yaml`.
- Politique de sync : `automated` avec `prune` et `selfHeal`, `CreateNamespace`, `ServerSideApply`, `ApplyOutOfSyncOnly`, réessais (15 tentatives, backoff 20 s x2 jusqu'à 6 min).
- `ignoreDifferences` sur les `WebhookConfiguration` de cert-manager, KEDA et istiod : leurs contrôleurs y injectent `caBundle` ; sans cela, les applications restent éternellement OutOfSync.
- Suivi des ressources par **annotation** (`application.resourceTrackingMethod: annotation`).
- `timeout.reconciliation: 60s` : le dépôt est relu toutes les minutes.
- Vagues (`argocd.argoproj.io/sync-wave`) : voir [architecture §6](../guide/02-architecture.md).

## Authentification
- Vers GitHub : aucune (dépôt public ; **observé** : aucun secret de type `repository`). Un dépôt privé exigerait une deploy key.
- Vers le cluster : ServiceAccounts propres (`argocd-application-controller`, etc.), droits très étendus (chart par défaut).
- UI : `admin` et le mot de passe du secret `argocd-initial-admin-secret` (`lab.sh ui`).
- La chart livre des **NetworkPolicies** pour Argo CD uniquement (seules NetworkPolicies du cluster, observé).

## Données traitées
Des manifestes Kubernetes (YAML rendus) et leur état réel. Pas de données d'utilisateurs. Le dépôt est **public** : aucune donnée sensible ne doit y être poussée.

## Contribution à l'inférence
Il garantit que la configuration de serving (modèle, arguments vLLM, scénario) **correspond à Git**, et la change à la demande : `lab.sh scenario x` modifie `gitops/active-azure.yaml`, pousse, et Argo CD recrée le `LLMInferenceService`.
Mesuré : un `scale` manuel à 0 d'un déploiement géré par Argo est annulé en 4 s (self-heal).

## Métriques à suivre
`argocd_app_info{health_status, sync_status}` (alerte `LabArgoAppUnhealthy`), `argocd_app_sync_total`, `argocd_git_request_total`. Le PodMonitor `lab-argocd` scrape les pods `part-of=argocd`.

## Pannes et diagnostic (observé)
| Symptôme | Cause / réponse |
|---|---|
| `ComparisonError ... unable to resolve parseableType ... Kind=Alertmanager` | CRDs de Prometheus pas encore là : se résout aux réessais |
| `failed to discover server resources for group version monitoring.coreos.com/v1` | idem pour Loki/Alloy qui créent des ServiceMonitors avant kube-prometheus-stack |
| application OutOfSync sur un webhook | `caBundle` injecté : `ignoreDifferences` |
| Application racine : YAML invalide après un `git push` | tout le GitOps se bloque ; lancer `tests/static.sh` **avant** de pousser (incident rencontré) |
| `applicationset-controller` présent alors que `applicationSet.enabled: false` | la clé de la chart ne l'a pas désactivé ; il est inutilisé (constat) |
