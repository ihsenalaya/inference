# Alertmanager et le récepteur d'alertes (`alert-sink`)

## Rôle
Reçoit les alertes de Prometheus, les **regroupe**, les **déduplique**, applique des **inhibitions** et les envoie à un récepteur. Version v0.35.0 (StatefulSet `alertmanager-kps-alertmanager`).

## Place dans l'architecture
Aval de Prometheus (règles `PrometheusRule`). Le récepteur par défaut est `alert-sink` (`mendhak/http-https-echo:39`, namespace `monitoring`) : il **journalise** chaque POST reçu.

## Configuration retenue (config : `gitops/observability/kube-prometheus-stack/values.yaml`)
- Route : récepteur `webhook`, regroupement par `alertname` et `model`, `group_wait 30s`, `group_interval 5m`, `repeat_interval 4h` ; `Watchdog` envoyée à un récepteur nul.
- **Inhibitions** : une alerte `LabScrapeTargetMissing` inhibe les alertes de catégorie `slo` du même `component` ; une alerte `critical` inhibe la `warning` de même nom et modèle.
- Récepteur `webhook` : `url_file` pointe vers le secret `alert-webhook` (monté dans le pod). Sans `ALERT_WEBHOOK_URL`, l'URL est celle d'`alert-sink`.
- Tests : `tests/promtool/lab_rules_test.yml` (promtool, 10 cas dont 5 de burn rate SLO). Test de bout en bout sur Azure : `LabRequestsWaiting`, `LabGPUIdleCost`, `EPPNoReadyEndpoints` et, le 17/11, `LabSLOBurnSlow` (classe `rag`) sont arrivées dans les logs d'`alert-sink` (les alertes `LabTTFTHigh` et `LabInterTokenLatencyHigh`, arrivées le 16/11, ont depuis été remplacées par les burn rates).

## Authentification
Aucune entre Prometheus et Alertmanager (interne). L'URL du webhook externe (Teams, Slack, ntfy) est un secret : elle contient souvent un jeton.

## Données traitées
Libellés et annotations d'alertes (nom, modèle, pod...). Pas de contenu de requête.

## Contribution à l'inférence
Indirecte : prévient d'une saturation, d'une erreur GPU ou d'un GPU inutilisé. **Les alertes de burn rate SLO ne sont pas encore écrites** (phase SLO) ; les alertes actuelles sont à seuils fixes larges.

## Métriques / pannes
`alertmanager_alerts`, `alertmanager_notifications_failed_total`. Si le webhook est injoignable, les alertes restent visibles dans l'UI mais ne sont pas livrées.
