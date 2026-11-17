# LeaderWorkerSet (LWS)

## Rôle
Contrôleur Kubernetes pour des groupes de pods « chef + travailleurs » (serving multi-nœud, parallélisme). Version **0.8.0**, namespace `lws-system`, 1 workload (`lws-controller-manager`, 20 m / 64 Mi).

## Place dans l'architecture
**Dépendance de KServe** v0.21.0 (installée par son script de dépendances). **Inutilisée** dans ce lab : un modèle tient sur un seul GPU, aucun serving multi-nœud (explicitement exclu).

## Relations
KServe pourrait créer des `LeaderWorkerSet` pour les déploiements multi-nœuds (champ `spec.worker`) ; nos scénarios n'utilisent que `spec.template`.

## Authentification / données
ServiceAccount et ClusterRole du chart ; aucune donnée d'inférence.

## Contribution à l'inférence
Aucune ici. Ne le supprimez pas sans vérifier la compatibilité de la version de KServe (CRD attendue).

## Métriques
Non suivies.
