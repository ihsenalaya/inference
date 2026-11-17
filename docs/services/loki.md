# Loki

**En une phrase.** Loki garde les textes que les programmes écrivent (les logs), classés par étiquettes, pour qu'on retrouve la cause d'une erreur.

<!-- mots: loki, alloy, pvc, namespace -->
> **Mots à connaître**
> - **Grafana / Loki / Alloy** : Tableaux de bord / stockage des logs / agent qui collecte les logs.
> - **PVC / disque persistant** : Demande de stockage qui survit au redémarrage d'un pod (disque managé Azure). Prometheus, Loki et PostgreSQL en ont un.
> - **Namespace** : Un « dossier » qui range les objets (`inference`, `gateway`, `monitoring`...).
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Rôle
Stocke et indexe les **logs** (par étiquettes, pas par contenu). Version 3.7.10, chart `grafana-community/loki` 21.2.3, mode **Monolithic** (un seul pod, `loki-0`).

## Place dans l'architecture
Namespace `monitoring`. Alimenté par Alloy ; lu par Grafana (datasource `Loki`).

## Configuration retenue (config : `gitops/observability/loki/values.yaml`)
- `deploymentMode: Monolithic`, `auth_enabled: false` (un seul locataire), stockage **filesystem** sur PVC 5 Gio (`managed-csi`), schéma `tsdb` v13, `replication_factor: 1`.
- Rétention **168 h (7 jours)** via le compacteur (`retention_enabled`).
- Caches, canary, gateway, MinIO : désactivés. Requests 100 m / 256 Mi, limite 768 Mi.
- `pattern_ingester` désactivé.

## Authentification
Aucune (multi-tenant désactivé). Écriture et lecture libres depuis le cluster.

## Données traitées
**Les logs de tous les pods**, y compris ceux de vLLM, de LiteLLM et les **access logs d'Envoy**. Ce sont des données potentiellement sensibles : les logs de LiteLLM/vLLM au niveau INFO n'incluent pas les prompts à notre connaissance (non vérifié ligne à ligne), mais tout log applicatif peut en contenir.

## Contribution à l'inférence
Diagnostic : erreurs CUDA/OOM de vLLM, causes d'erreurs 500 (`response_code_details` d'Envoy), événements de scheduling et de pull d'image. Vérifié sur Azure : logs vLLM, access logs Envoy, logs LiteLLM et événements Kubernetes tous interrogeables.

## Métriques
`loki_*` (ServiceMonitor activé) ; surveiller le disque (`kubelet_volume_stats_used_bytes` du PVC `storage-loki-0`).

## Pannes
PVC plein (5 Gio) : baisse de la rétention ou augmentation du volume. Valeurs du chart refusées si une clé inexistante est fournie (le schéma de la chart est strict ; rencontré avec `minio` et `bloomCompactor`).
