# Grafana

**En une phrase.** Grafana est l'écran de contrôle : il affiche en graphiques ce que Prometheus (chiffres) et Loki (logs) ont enregistré.

<!-- mots: dashboard, annotation, métrique, gitops -->
> **Mots à connaître**
> - **Dashboard / panneau / annotation** : Page Grafana / un graphique / un repère de temps (début et fin d'un bench).
> - **Métrique** : Un nombre mesuré dans le temps (ex. `vllm:num_requests_waiting`). *Counter* = ne fait que monter ; *gauge* = monte et descend.
> - **GitOps** : L'état voulu du cluster est écrit dans Git ; Argo CD le fait appliquer. On ne modifie pas le cluster à la main.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Rôle
Interface de visualisation : dashboards sur Prometheus et Loki, exploration des logs, annotations. Version 13.3.1 (image distroless), déployé par le chart kube-prometheus-stack.

## Place dans l'architecture
Namespace `monitoring`, accessible par `lab.sh ui` (port 3000). Lit Prometheus, Loki et Alertmanager.

## Composants
Un pod à trois conteneurs : `grafana` + deux **sidecars** `k8s-sidecar` (2.14.3) qui surveillent l'API Kubernetes : `grafana-sc-dashboard` (ConfigMaps étiquetées `grafana_dashboard=1`, tous namespaces) et `grafana-sc-datasources`.

## Configuration retenue (config)
- Identifiants : secret `grafana-admin` (créé par Terraform) via `admin.existingSecret`.
- **Dashboards = code** : `gitops/observability/config/dashboards/**.json` -> chart -> une ConfigMap par dashboard (`grafana_dashboard: "1"`, annotation `grafana_folder`) -> le sidecar les charge. 9 dashboards « Lab » (générés par `tests/gen_dashboards.py`, dont « 06 - SLO par classe de charge », « 07 - Santé du GPU » et « 08 - Efficacité et goulot du GPU »), 5 de llm-d, 1 DCGM (voir [guide §4](../guide/04-observabilite.md)).
- Datasources : `Prometheus` (uid `prometheus`), `Loki` (uid `loki`, `http://loki.monitoring.svc:3100`), `Alertmanager`.
- Pas de persistance (`persistence.enabled: false`) : tout est reconstruit depuis Git. Modifier un dashboard dans l'UI **ne survit pas** : éditer le générateur ou le JSON.
- Fuseau `Europe/Paris`.

## Authentification
Compte `admin` local ; pas de SSO. Accès par port-forward uniquement.

## Données traitées
Requêtes PromQL/LogQL et leurs résultats ; aucun stockage de métriques ni de logs.

## Contribution à l'inférence
Lecture et diagnostic : c'est là qu'on voit file, latences, GPU, coût. Les **annotations** posées par `lab.sh bench` y délimitent chaque run.

## Pannes et diagnostic (observé)
- Dashboards « No data » : cible Prometheus absente ou nom de métrique erroné ; vérifier avec `tests/check_panels.py` (72 panneaux Prometheus sur 74 avec données le 17/11 ; les 2 vides étaient les panneaux « budget consommé » de classes sans trafic récent : normal).
- Dashboard importé sans datasource : remplacer `${DS_PROMETHEUS}` par l'uid `prometheus` (`tests/normalize_imported_dashboards.py`).
