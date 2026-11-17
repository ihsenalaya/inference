# LeaderWorkerSet (LWS)

**En une phrase.** LeaderWorkerSet sert à faire tourner un modèle trop gros pour un seul GPU (un groupe de pods « chef + ouvriers »). Il est installé parce que KServe l'exige, mais **il n'est pas utilisé** ici.

<!-- mots: kserve, pod, crd -->
> **Mots à connaître**
> - **KServe / `LLMInferenceService`** : Un seul objet déclare un modèle ; KServe crée les pods, le routage et le choix du pod.
> - **Pod** : La plus petite unité qui tourne : un ou plusieurs conteneurs. Un pod vLLM = un modèle sur un GPU.
> - **CRD / opérateur** : Nouveau type d'objet ajouté à Kubernetes / programme qui gère ces objets (ex. `LLMInferenceService`).
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

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
