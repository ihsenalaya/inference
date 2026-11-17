# PostgreSQL (base de LiteLLM)

**En une phrase.** PostgreSQL est le carnet de LiteLLM : il garde les clés, les équipes et la consommation de chacun.

<!-- mots: litellm, clé virtuelle, pvc, secret -->
> **Mots à connaître**
> - **LiteLLM** : Passerelle OpenAI-compatible : clés virtuelles, budgets, limites, métriques par client.
> - **Clé virtuelle** : Clé d'API LiteLLM par client ; l'alias de la clé sert ici à identifier la **classe de charge**.
> - **PVC / disque persistant** : Demande de stockage qui survit au redémarrage d'un pod (disque managé Azure). Prometheus, Loki et PostgreSQL en ont un.
> - **ConfigMap / Secret** : Configuration / données sensibles (mots de passe, clés) injectées dans les pods.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Rôle
Stocke l'état de LiteLLM : **clés virtuelles, équipes, budgets, dépenses**. Sans base, LiteLLM n'a pas de clés virtuelles ni de suivi de budget (doc LiteLLM).

## Place dans l'architecture
Namespace `gateway`, StatefulSet `postgres` (image `postgres:16.11-alpine`, 1 réplica), Service headless `postgres:5432`. Pool système.

## Relations
LiteLLM seul s'y connecte (`DATABASE_URL`). Aucune autre dépendance.

## Configuration retenue (config : `gitops/gateway/postgres/postgres.yaml`)
Utilisateur et base `litellm`, mot de passe `POSTGRES_PASSWORD` (secret `litellm-secrets`), `PGDATA=/var/lib/postgresql/data/pgdata`. Volume : PVC 2 Gio (classe `default`, observé). Ressources : requests 50 m / 128 Mi, limite 384 Mi. Sonde : `pg_isready`.

## Authentification
Mot de passe sur le protocole PostgreSQL ; pas de TLS (trafic interne en clair). Accessible depuis tout pod du cluster qui connaît le mot de passe (aucune NetworkPolicy).

## Données traitées
Métadonnées de gestion (équipes, clés hachées/chiffrées par la salt key, compteurs de dépense). Volume mesuré : ~51-97 Mi de mémoire en charge.

## Contribution à l'inférence
Indirecte : permet l'authentification et les quotas. Si PostgreSQL est indisponible, LiteLLM devient non prêt (`/health/readiness`) et les requêtes ne sont plus servies (comportement à confirmer par game day).

## Métriques
Pas d'exporteur PostgreSQL déployé : surveiller l'état du pod, la mémoire et le disque (`kubelet_volume_stats_*`).

## Pannes et persistance
Le PVC survit à `stop` ; il est supprimé par `down` (les clés sont régénérées au prochain `up`). **Aucune sauvegarde** automatique (voir [cycle de vie](../guide/06-cycle-de-vie-et-couts.md)).
