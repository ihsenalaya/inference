# Alertmanager et le récepteur d'alertes (`alert-sink`)

**En une phrase.** Alertmanager reçoit les alertes de Prometheus, évite les doublons et les envoie à une adresse (ici un récepteur interne qui les écrit simplement dans ses logs).

<!-- mots: alerte, webhook, runbook, slo, burn rate -->
> **Mots à connaître**
> - **Alerte / runbook** : Notification d'un problème / fiche qui dit quoi vérifier et quoi faire (`docs/runbooks/`).
> - **Webhook** : Adresse HTTP qui reçoit des messages d'un autre programme (ici : les alertes d'Alertmanager).
> - **SLO** : Un objectif chiffré de qualité de service, par exemple « 95 % des réponses commencent en moins de 5 s ».
> - **Burn rate** : Vitesse de consommation du budget : 1 = on l'épuise juste à la fin de la fenêtre ; 14,4 = en ~50 h pour une fenêtre de 30 jours.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

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
Indirecte : prévient d'une saturation, d'une erreur GPU, d'un GPU inutilisé et, depuis le 17/11, d'une consommation trop rapide du budget d'erreur d'une classe de charge (`LabSLOBurnFast` et `LabSLOBurnSlow`, voir [module 4](../formation/04-burn-rate-et-alertes.md)). Les autres alertes ont des seuils fixes larges.

## Métriques / pannes
`alertmanager_alerts`, `alertmanager_notifications_failed_total`. Si le webhook est injoignable, les alertes restent visibles dans l'UI mais ne sont pas livrées.
