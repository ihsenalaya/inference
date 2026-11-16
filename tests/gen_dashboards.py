#!/usr/bin/env python3
"""Génère les dashboards Grafana du lab (JSON) dans gitops/observability/config/dashboards/.

Chaque panneau a un titre, une unité et une description (ce qu'il mesure, quel levier d'optimisation il éclaire).
Lancer : python3 tests/gen_dashboards.py   (puis commit des JSON ; ils sont chargés en ConfigMaps par le chart).
"""
import json, os, pathlib

OUT = pathlib.Path(__file__).resolve().parent.parent / "gitops/observability/config/dashboards"
OUT.mkdir(parents=True, exist_ok=True)
PROM = {"type": "prometheus", "uid": "prometheus"}
LOKI = {"type": "loki", "uid": "loki"}
M = '{model_name=~"$model"}'


class D:
    def __init__(self, uid, title, folder, desc, tags=None):
        self.uid, self.title, self.folder, self.desc = uid, title, folder, desc
        self.panels, self.y, self.x, self.id, self.rowh = [], 0, 0, 1, 0
        self.tags = ["lab"] + (tags or [])

    def row(self, title):
        if self.x:
            self.y += self.rowh; self.x = 0; self.rowh = 0
        self.panels.append({"id": self.id, "type": "row", "title": title, "collapsed": False,
                            "gridPos": {"h": 1, "w": 24, "x": 0, "y": self.y}, "panels": []})
        self.id += 1; self.y += 1

    def _place(self, w, h):
        if self.x + w > 24:
            self.y += self.rowh; self.x = 0; self.rowh = 0
        pos = {"h": h, "w": w, "x": self.x, "y": self.y}
        self.x += w; self.rowh = max(self.rowh, h)
        if self.x >= 24:
            self.y += self.rowh; self.x = 0; self.rowh = 0
        return pos

    def ts(self, title, desc, exprs, unit="short", w=8, h=7, stack=False, ds=PROM, minv=None, maxv=None):
        p = {"id": self.id, "type": "timeseries", "title": title, "description": desc, "datasource": ds,
             "gridPos": self._place(w, h),
             "targets": [{"refId": chr(65 + i), "expr": e, "legendFormat": l, "datasource": ds} for i, (e, l) in enumerate(exprs)],
             "fieldConfig": {"defaults": {"unit": unit, "custom": {"fillOpacity": 15 if stack else 8, "lineWidth": 1,
                             "stacking": {"mode": "normal" if stack else "none"}}, **({"min": minv} if minv is not None else {}),
                             **({"max": maxv} if maxv is not None else {})}, "overrides": []},
             "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}}}
        self.panels.append(p); self.id += 1

    def stat(self, title, desc, expr, unit="short", w=4, h=4, thresholds=None):
        steps = thresholds or [{"color": "green", "value": None}]
        self.panels.append({"id": self.id, "type": "stat", "title": title, "description": desc, "datasource": PROM,
                            "gridPos": self._place(w, h), "targets": [{"refId": "A", "expr": expr, "datasource": PROM}],
                            "fieldConfig": {"defaults": {"unit": unit, "thresholds": {"mode": "absolute", "steps": steps}}, "overrides": []},
                            "options": {"reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "value"}})
        self.id += 1

    def heat(self, title, desc, metric, unit="s", w=12, h=8):
        self.panels.append({"id": self.id, "type": "heatmap", "title": title, "description": desc, "datasource": PROM,
                            "gridPos": self._place(w, h),
                            "targets": [{"refId": "A", "expr": f'sum by (le) (increase({metric}_bucket{M}[$__rate_interval]))',
                                         "format": "heatmap", "legendFormat": "{{le}}", "datasource": PROM}],
                            "options": {"calculate": False, "yAxis": {"unit": unit}, "color": {"scheme": "Spectral"}}})
        self.id += 1

    def logs(self, title, desc, expr, w=24, h=10):
        self.panels.append({"id": self.id, "type": "logs", "title": title, "description": desc, "datasource": LOKI,
                            "gridPos": self._place(w, h), "targets": [{"refId": "A", "expr": expr, "datasource": LOKI}],
                            "options": {"showTime": True, "wrapLogMessage": True, "enableLogDetails": True}})
        self.id += 1

    def save(self, vars_model=True):
        tv = [{"name": "model", "type": "query", "datasource": PROM, "query": {"query": "label_values(vllm:num_requests_running, model_name)", "refId": "m"},
               "refresh": 2, "includeAll": True, "allValue": ".*", "multi": True, "current": {"text": "All", "value": "$__all"}},
              {"name": "pod", "type": "query", "datasource": PROM, "query": {"query": "label_values(vllm:num_requests_running, pod)", "refId": "p"},
               "refresh": 2, "includeAll": True, "allValue": ".*", "multi": True, "current": {"text": "All", "value": "$__all"}},
              {"name": "namespace", "type": "query", "datasource": PROM, "query": {"query": "label_values(vllm:num_requests_running, namespace)", "refId": "n"},
               "refresh": 2, "includeAll": True, "allValue": ".*", "multi": True, "current": {"text": "All", "value": "$__all"}}]
        dash = {"uid": self.uid, "title": self.title, "description": self.desc, "tags": self.tags, "schemaVersion": 39, "version": 1,
                "editable": True, "time": {"from": "now-1h", "to": "now"}, "refresh": "30s", "timezone": "browser",
                "templating": {"list": tv if vars_model else []}, "panels": self.panels,
                "annotations": {"list": [{"builtIn": 1, "datasource": {"type": "grafana", "uid": "-- Grafana --"}, "enable": True,
                                          "hide": False, "iconColor": "rgba(0, 211, 255, 1)", "name": "Annotations & Alerts", "type": "dashboard"}]}}
        d = OUT / self.folder
        d.mkdir(exist_ok=True)
        (d / f"{self.uid}.json").write_text(json.dumps(dash, indent=1, ensure_ascii=False))


def q(fn, metric, extra=""):
    return f'{fn}(sum by (le, model_name) (rate({metric}_bucket{M}[$__rate_interval])))' if False else None


def hq(p, metric):
    return f'histogram_quantile({p}, sum by (le, model_name) (rate({metric}_bucket{M}[$__rate_interval])))'


# ---------------- 00 Cockpit ----------------
d = D("lab-cockpit", "00 - Cockpit d'optimisation", "Lab", "Une ligne par question : utilisateurs servis ? saturation ? GPU ? efficacité ? routage ? autoscaling ?")
d.row("1. Les utilisateurs sont-ils bien servis ?")
for p, n in (("0.5", "p50"), ("0.95", "p95"), ("0.99", "p99")):
    pass
d.ts("TTFT (p50 / p95 / p99)", "Délai avant le premier token. Levier : prefill (max-num-batched-tokens, cache de préfixes, taille du prompt), file d'attente, backend d'attention.",
     [(hq(0.5, "vllm:time_to_first_token_seconds"), "p50 {{model_name}}"), (hq(0.95, "vllm:time_to_first_token_seconds"), "p95 {{model_name}}"),
      (hq(0.99, "vllm:time_to_first_token_seconds"), "p99 {{model_name}}")], "s")
d.ts("Latence inter-token (p50 / p95)", "Temps entre deux tokens générés. Levier : taille du batch (max-num-seqs), quantization, bande passante mémoire du GPU.",
     [(hq(0.5, "vllm:inter_token_latency_seconds"), "p50 {{model_name}}"), (hq(0.95, "vllm:inter_token_latency_seconds"), "p95 {{model_name}}")], "s")
d.ts("Latence de bout en bout (p50 / p95 / p99)", "Durée totale d'une requête. Levier : longueur de génération, file d'attente, nombre de réplicas.",
     [(hq(0.5, "vllm:e2e_request_latency_seconds"), "p50 {{model_name}}"), (hq(0.95, "vllm:e2e_request_latency_seconds"), "p95 {{model_name}}"),
      (hq(0.99, "vllm:e2e_request_latency_seconds"), "p99 {{model_name}}")], "s")
d.ts("Taux d'erreur (LiteLLM)", "Part des requêtes en échec vu de la passerelle. Levier : timeouts, OOM, saturation, fallback LiteLLM.",
     [('sum(rate(litellm_proxy_failed_requests_metric_total[$__rate_interval])) / sum(rate(litellm_proxy_total_requests_metric_total[$__rate_interval]))', "erreurs")], "percentunit")
d.ts("Requêtes par seconde", "Débit de requêtes terminées avec succès par modèle.", [(f'sum by (model_name) (rate(vllm:request_success_total{M}[$__rate_interval]))', "{{model_name}}")], "reqps")
d.ts("Requêtes LiteLLM par équipe", "Trafic par équipe (lab-bench / lab-user) : quotas et budgets.", [('sum by (team_alias) (rate(litellm_requests_metric_total[$__rate_interval]))', "{{team_alias}}")], "reqps")
d.row("2. Le système sature-t-il ?")
d.ts("Requêtes en cours / en attente", "Running = batch courant ; waiting = file. Une file qui monte = capacité insuffisante : max-num-seqs, réplicas, KEDA.",
     [(f'sum by (model_name) (vllm:num_requests_running{M})', "running {{model_name}}"), (f'sum by (model_name) (vllm:num_requests_waiting{M})', "waiting {{model_name}}")])
d.ts("Temps de file (p95)", "Temps passé en attente avant le prefill.", [(hq(0.95, "vllm:request_queue_time_seconds"), "p95 {{model_name}}")], "s")
d.ts("Usage du cache KV", "Proche de 100 % = préemptions et latence. Levier : max-model-len, gpu-memory-utilization, quantization du modèle, cache KV.",
     [(f'max by (model_name, pod) (vllm:kv_cache_usage_perc{M})', "{{model_name}} {{pod}}")], "percentunit", minv=0, maxv=1)
d.ts("Préemptions par seconde", "Requêtes évincées faute de place dans le cache KV : signe de sous-dimensionnement mémoire.", [(f'sum by (model_name) (rate(vllm:num_preemptions_total{M}[$__rate_interval]))', "{{model_name}}")], "ops")
d.row("3. Le GPU travaille-t-il ?")
d.ts("Utilisation GPU", "DCGM_FI_DEV_GPU_UTIL : fraction du temps avec un noyau actif (pas la saturation). Voir aussi l'activité moteur dans le dashboard GPU.", [("DCGM_FI_DEV_GPU_UTIL", "GPU {{gpu}} {{Hostname}}")], "percent", minv=0, maxv=100)
d.ts("Mémoire GPU utilisée", "Poids + cache KV. Levier : gpu-memory-utilization, max-model-len, quantization.", [("DCGM_FI_DEV_FB_USED * 1024 * 1024", "utilisée {{gpu}}"), ("DCGM_FI_DEV_FB_FREE * 1024 * 1024", "libre {{gpu}}")], "bytes", stack=True)
d.ts("Puissance (W) et température", "Un T4 est limité à 70 W : un GPU au plafond de puissance est limité par son enveloppe énergétique.", [("DCGM_FI_DEV_POWER_USAGE", "W {{gpu}}"), ("DCGM_FI_DEV_GPU_TEMP", "°C {{gpu}}")])
d.row("4. Est-ce efficace ?")
d.ts("Tokens générés par seconde", "Débit de génération par modèle.", [("lab:generation_tokens:rate1m", "{{model_name}}")], "short")
d.ts("Tokens par seconde et par GPU", "Efficacité matérielle. Comparer les scénarios (quantization, taille de batch).", [("lab:tokens_per_second_per_gpu", "tok/s/GPU")], "short")
d.ts("Tokens par joule", "Efficacité énergétique (DCGM énergie cumulée).", [("lab:tokens_per_joule", "tok/J")], "short")
d.ts("Coût par million de tokens", "(nœuds GPU x prix horaire) / tokens par heure x 1e6. Le plus bas est le meilleur ; très sensible à l'utilisation.", [("lab:cost_per_million_tokens_usd", "$ / M tokens")], "currencyUSD")
d.ts("Part d'inactivité GPU", "1 - utilisation moyenne. Un GPU inactif coûte le même prix : levier = stop / scale à 0, autoscaling.", [("lab:gpu_idle_ratio", "inactif")], "percentunit", minv=0, maxv=1)
d.row("5. Le routage est-il bon ?")
d.ts("Charge par pod", "Répartition running + waiting entre réplicas : un écart durable = scorers de l'EPP à régler.", [(f'sum by (pod) (vllm:num_requests_running{M} + vllm:num_requests_waiting{M})', "{{pod}}")])
d.ts("Taux de hit du cache de préfixes", "hits / queries. Levier : poids du scorer de préfixes de l'EPP, prompts avec préfixe commun.", [("lab:prefix_cache_hit_ratio", "{{model_name}}")], "percentunit", minv=0, maxv=1)
d.ts("Écart de charge entre réplicas", "max - min de la charge par réplica.", [("lab:replica_load_gap", "{{model_name}}")])
d.row("6. L'autoscaling suit-il ?")
d.ts("Réplicas désirés / prêts", "HPA géré par KEDA : désiré vs prêt. L'écart = temps de chargement du modèle (cold start).",
     [('kube_horizontalpodautoscaler_status_desired_replicas{namespace="inference"}', "désirés {{horizontalpodautoscaler}}"),
      ('kube_horizontalpodautoscaler_status_current_replicas{namespace="inference"}', "courants {{horizontalpodautoscaler}}")])
d.ts("Valeur du trigger KEDA", "Valeur de la requête Prometheus du ScaledObject.", [('keda_scaler_metrics_value', "{{scaledObject}}")])
d.ts("Événements de scaling", "Changements de réplicas.", [('changes(kube_deployment_status_replicas{namespace="inference"}[$__rate_interval])', "{{deployment}}")])
d.save()

# ---------------- 01 Anatomie d'une requête ----------------
d = D("lab-anatomy", "01 - Anatomie d'une requête", "Lab", "Décomposition du temps d'une requête : LiteLLM, Gateway, EPP, file vLLM, prefill, decode.")
d.row("Décomposition du temps (p95)")
d.ts("Où va le temps ?", "File + prefill + decode côté vLLM, plus surcoût LiteLLM. Montre quel étage optimiser.",
     [(hq(0.95, "vllm:request_queue_time_seconds"), "file {{model_name}}"), (hq(0.95, "vllm:request_prefill_time_seconds"), "prefill {{model_name}}"),
      (hq(0.95, "vllm:request_decode_time_seconds"), "decode {{model_name}}"), ("lab:litellm_overhead_seconds:p95", "surcoût LiteLLM")], "s", w=12, stack=True)
d.ts("Surcoût de la Gateway Istio (p95)", "Latence ajoutée par Envoy (istio_request_duration) vs vLLM.", [('histogram_quantile(0.95, sum by (le) (rate(istio_request_duration_milliseconds_bucket{reporter="source"}[$__rate_interval]))) / 1000', "Gateway p95")], "s", w=12)
d.row("Distributions")
d.heat("TTFT", "Histogramme du TTFT (heatmap).", "vllm:time_to_first_token_seconds")
d.heat("Latence de bout en bout", "Histogramme de la latence totale.", "vllm:e2e_request_latency_seconds")
d.heat("Temps de file", "Histogramme du temps en file.", "vllm:request_queue_time_seconds")
d.heat("Prefill", "Histogramme du temps de prefill.", "vllm:request_prefill_time_seconds")
d.row("Tailles")
d.ts("Tokens de prompt par seconde", "Charge de prefill.", [("lab:prompt_tokens:rate1m", "{{model_name}}")], w=12)
d.ts("Tokens générés par seconde", "Charge de decode.", [("lab:generation_tokens:rate1m", "{{model_name}}")], w=12)
d.ts("Taille moyenne des prompts / générations", "Tokens moyens par requête.", [(f'sum(rate(vllm:prompt_tokens_total{M}[$__rate_interval])) / sum(rate(vllm:request_success_total{M}[$__rate_interval]))', "prompt"),
     (f'sum(rate(vllm:generation_tokens_total{M}[$__rate_interval])) / sum(rate(vllm:request_success_total{M}[$__rate_interval]))', "génération")], w=12)
d.ts("Décision de l'EPP", "Durée de décision du scheduler llm-d (inference_extension_scheduler_e2e_duration_seconds).", [("lab:epp_decision_seconds:p95", "EPP scheduler p95")], "s", w=12)
d.save()

# ---------------- 02 GPU en profondeur ----------------
d = D("lab-gpu", "02 - GPU en profondeur", "Lab", "Par GPU, nœud et pod : utilisation face à l'activité moteur, mémoire, énergie, erreurs, PCIe.")
d.row("Charge")
d.ts("Utilisation vs activité du moteur graphique", "GPU_UTIL dit « un noyau tourne » ; PROF_GR_ENGINE_ACTIVE dit « le moteur est réellement occupé ». Un grand écart = noyaux peu efficaces.",
     [("DCGM_FI_DEV_GPU_UTIL / 100", "GPU_UTIL {{gpu}}"), ("DCGM_FI_PROF_GR_ENGINE_ACTIVE", "ENGINE_ACTIVE {{gpu}}")], "percentunit", w=12, minv=0, maxv=1)
d.ts("Activité DRAM (bande passante mémoire)", "Le decode est limité par la bande passante mémoire : proche de 1 = on a atteint la limite du T4 (320 Go/s).", [("DCGM_FI_PROF_DRAM_ACTIVE", "DRAM {{gpu}}")], "percentunit", w=12, minv=0, maxv=1)
d.row("Mémoire")
d.ts("Mémoire utilisée / libre", "Framebuffer du GPU (16 Go sur T4).", [("DCGM_FI_DEV_FB_USED * 1024 * 1024", "utilisée {{gpu}}"), ("DCGM_FI_DEV_FB_FREE * 1024 * 1024", "libre {{gpu}}")], "bytes", w=12, stack=True)
d.ts("Mémoire par pod", "Jointure DCGM / pod (honorLabels) : qui consomme la mémoire.", [("sum by (pod) (DCGM_FI_DEV_FB_USED) * 1024 * 1024", "{{pod}}")], "bytes", w=12)
d.row("Énergie et thermique")
d.ts("Puissance", "Plafond du T4 : 70 W.", [("DCGM_FI_DEV_POWER_USAGE", "{{gpu}}")], "watt", w=8)
d.ts("Énergie cumulée (taux)", "Watts moyens via le compteur d'énergie.", [("rate(DCGM_FI_DEV_TOTAL_ENERGY_CONSUMPTION[$__rate_interval]) / 1000", "{{gpu}}")], "watt", w=8)
d.ts("Température", "Au-delà de ~85 °C le GPU réduit ses fréquences.", [("DCGM_FI_DEV_GPU_TEMP", "{{gpu}}")], "celsius", w=8)
d.row("Fiabilité et PCIe")
d.ts("Erreurs XID / ECC / rejeux PCIe", "Doivent rester à zéro.", [("DCGM_FI_DEV_XID_ERRORS", "XID {{gpu}}"), ("DCGM_FI_DEV_ECC_DBE_VOL_TOTAL", "ECC DBE {{gpu}}"), ("increase(DCGM_FI_DEV_PCIE_REPLAY_COUNTER[$__rate_interval])", "PCIe replay {{gpu}}")], w=8)
d.ts("Raisons de throttling", "Bitmask des raisons de bridage (puissance, thermique...).", [("DCGM_FI_DEV_CLOCK_THROTTLE_REASONS", "{{gpu}}")], w=8)
d.ts("PCIe TX / RX", "Trafic PCIe (chargement du modèle, copies).", [("rate(DCGM_FI_PROF_PCIE_TX_BYTES[$__rate_interval])", "TX {{gpu}}"), ("rate(DCGM_FI_PROF_PCIE_RX_BYTES[$__rate_interval])", "RX {{gpu}}")], "Bps", w=8)
d.row("Corrélation")
d.ts("Utilisation GPU vs tokens/s", "Si les tokens/s montent sans que l'utilisation GPU suive, le goulot n'est pas le GPU.", [("avg(DCGM_FI_DEV_GPU_UTIL)", "GPU util (%)"), ("sum(lab:generation_tokens:rate1m)", "tokens/s")], w=24)
d.save(vars_model=False)

# ---------------- 03 Capacité et coût ----------------
d = D("lab-capacity", "03 - Capacité et coût", "Lab", "Débit maximal observé, coût horaire, coût par million de tokens, temps GPU inactif, délais de cold start.")
d.row("Capacité")
d.stat("Débit max observé (tok/s, 24 h)", "Maximum de tokens générés par seconde sur la fenêtre.", "max_over_time(sum(lab:generation_tokens:rate1m)[24h:1m])", "short")
d.stat("Nombre de GPU", "GPU visibles par DCGM.", "lab:gpu_count", "short")
d.stat("Coût horaire des GPU", "Nombre de GPU x prix horaire (ConfigMap exposé en métrique).", "lab:gpu_count * lab:gpu_hourly_price_usd", "currencyUSD")
d.stat("Coût / million de tokens", "Voir cockpit.", "lab:cost_per_million_tokens_usd", "currencyUSD")
d.stat("Part d'inactivité GPU", "1 - utilisation moyenne.", "lab:gpu_idle_ratio", "percentunit")
d.ts("Coût cumulé estimé (par heure)", "Coût horaire des GPU dans le temps.", [("lab:gpu_count * lab:gpu_hourly_price_usd", "$/h")], "currencyUSD", w=12)
d.ts("Débit par modèle", "Tokens/s par modèle.", [("lab:generation_tokens:rate1m", "{{model_name}}")], w=12)
d.row("Cold start")
d.ts("Phases de démarrage d'un pod vLLM", "Durées Kubernetes : planification, pull d'image, démarrage conteneur, ready. Mesurées par kube-state-metrics.",
     [('kube_pod_status_ready_time{namespace="inference"} - kube_pod_created{namespace="inference"}', "created → ready {{pod}}"),
      ('kube_pod_start_time{namespace="inference"} - kube_pod_created{namespace="inference"}', "created → start {{pod}}")], "s", w=24)
d.save(vars_model=False)

# ---------------- 04 Comparaison de runs ----------------
d = D("lab-compare", "04 - Comparaison de runs", "Lab", "Avant / après : les annotations de bench (profil, scénario, SHA Git, paramètres vLLM) délimitent chaque run.")
d.row("Comparer deux plages de temps")
d.ts("TTFT p95", "Sélectionner deux plages via les annotations de bench.", [("lab:ttft_seconds:p95", "{{model_name}}")], "s", w=12)
d.ts("Tokens/s", "Débit.", [("lab:generation_tokens:rate1m", "{{model_name}}")], w=12)
d.ts("Inter-token p95", "Latence de décodage.", [("lab:itl_seconds:p95", "{{model_name}}")], "s", w=12)
d.ts("Coût par million de tokens", "Efficacité économique.", [("lab:cost_per_million_tokens_usd", "$ / M")], "currencyUSD", w=12)
d.ts("Cache de préfixes", "Hit ratio.", [("lab:prefix_cache_hit_ratio", "{{model_name}}")], "percentunit", w=12)
d.ts("Charge par pod", "Équilibre du routage.", [("lab:replica_load_gap", "{{model_name}}")], w=12)
d.save()

# ---------------- 05 Logs ----------------
d = D("lab-logs", "05 - Logs", "Lab", "Loki : erreurs vLLM, événements Kubernetes, access logs de la gateway, alignés sur le temps des métriques.")
d.row("Erreurs et événements")
d.logs("Logs vLLM (erreurs)", "Lignes ERROR / Traceback / OOM des pods vLLM.", '{namespace="inference", container="main"} |~ "(?i)error|traceback|oom|cuda"')
d.logs("Événements Kubernetes", "Événements du cluster (scheduling, pull, probes).", '{job=~".*events.*"} or {namespace="inference"} |= "Warning"')
d.logs("Access logs de la gateway Istio", "JSON Envoy : code, durée, upstream.", '{namespace="inference", container="istio-proxy"}')
d.ts("Débit de logs d'erreur", "Erreurs par minute, alignées sur les métriques.", [('sum by (pod) (count_over_time({namespace="inference"} |~ "(?i)error" [1m]))', "{{pod}}")], ds=LOKI, w=24)
d.save(vars_model=False)

print("ok", sorted(str(p.relative_to(OUT)) for p in OUT.rglob("*.json")))
