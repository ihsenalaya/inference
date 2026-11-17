# cert-manager

## Rôle
Émet et renouvelle des **certificats TLS** pour les composants du cluster.

## Place dans l'architecture
Prérequis de KServe : le contrôleur `llmisvc` expose un **webhook d'admission** (validation et mutation des `LLMInferenceService`) en HTTPS ; son certificat est géré par cert-manager.
Version **v1.17.4** : la mineure 1.17 est imposée par la version de KServe (v0.21.0).

## Relations
KServe -> cert-manager : `Issuer selfsigned-issuer` + `Certificate llmisvc-serving-cert` (namespace `kserve`, observé) -> secret `llmisvc-webhook-server-cert`. L'API server appelle le webhook de KServe avec ce certificat ; le `cainjector` écrit le CA dans la `WebhookConfiguration`.

## Configuration retenue
`crds.enabled: true`, ressources minimales (20 m CPU), métriques Prometheus activées (ServiceMonitor `lab-cert-manager`). Trois workloads : `cert-manager` (contrôleur), `cert-manager-cainjector`, `cert-manager-webhook`.

## Authentification
ServiceAccounts propres. Les certificats sont **auto-signés** (pas d'AC externe, pas d'ACME).

## Données traitées
Des objets `Certificate`/`Secret` TLS. Aucune donnée d'application.

## Contribution à l'inférence
**Indirecte** : sans cert-manager, le webhook de KServe n'est pas servi et les `LLMInferenceService` ne peuvent pas être créés. Le trafic d'inférence lui-même ne passe pas en TLS géré par cert-manager dans ce lab (le TLS interne de KServe est **désactivé** : les probes du pod vLLM sont en HTTP ; observé).

## Métriques
`certmanager_certificate_ready_status`, `certmanager_certificate_expiration_timestamp_seconds` (non regardées dans les dashboards actuels).

## Pannes
Un certificat non prêt bloque l'admission des `LLMInferenceService` : `kubectl -n kserve get certificate`.
