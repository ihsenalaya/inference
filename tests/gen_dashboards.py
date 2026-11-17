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
     [('(sum(rate(litellm_proxy_failed_requests_metric_total[$__rate_interval])) or vector(0)) / sum(rate(litellm_proxy_total_requests_metric_total[$__rate_interval]))', "erreurs")], "percentunit")
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
d.ts("Réplicas désirés / prêts", "Deployment du modèle : réplicas voulus (HPA/KEDA ou fixes) vs prêts. L'écart = temps de chargement du modèle (cold start).",
     [('sum by (deployment) (kube_deployment_spec_replicas{namespace="inference", deployment=~".*kserve$"})', "désirés {{deployment}}"),
      ('sum by (deployment) (kube_deployment_status_replicas_ready{namespace="inference", deployment=~".*kserve$"})', "prêts {{deployment}}")])
d.ts("Valeur du trigger KEDA", "Valeur de la requête Prometheus du ScaledObject (0 quand le scénario n'utilise pas KEDA).", [('keda_scaler_metrics_value or on() vector(0)', "trigger")])
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
d.row("CPU, allocation et utilisation")
d.ts("CPU du pod vLLM vs activité GPU", "Le CPU limite-t-il le GPU ? Un pod proche de ses cœurs disponibles avec un moteur graphique peu actif = goulot CPU (tokenisation, serveur d'API, streaming). Un T4 NC4as n'a que 4 cœurs.",
     [("lab:vllm_cpu_cores", "CPU vLLM (cœurs) {{pod}}"), ("DCGM_FI_PROF_GR_ENGINE_ACTIVE * 4", "activité moteur x4 (échelle comparable)")], w=12)
d.ts("Périodes CFS bridées (CPU throttling)", "Part des périodes où le conteneur vLLM a été bridé par sa limite CPU (0 si aucune limite : voir requests/limits).", [("lab:vllm_cpu_throttled_ratio or on() vector(0)", "{{pod}}")], "percentunit", w=12, minv=0)
d.ts("GPU : capacité / allouable / alloué / utilisé", "Quatre chiffres à distinguer. Alloué sans être utilisé = coût sans service (voir alerte LabGPUIdleCost).", [("lab:gpu_capacity", "capacité"), ("lab:gpu_allocatable", "allouable"), ("lab:gpu_allocated", "alloué (pods)"), ("lab:gpu_used", "utilisé (>5 % d'utilisation)")], w=24)
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

# ---------------- 06 SLO par classe ----------------
d = D("lab-slo", "06 - SLO par classe de charge", "Lab", "Budget d'erreur, burn rate et goodput par classe (interactive, rag, multiturn, batch). SLO : docs/sre/SLO.md. La classe = alias de la clé virtuelle LiteLLM.")
d.row("Burn rate (1 = on consomme le budget exactement au rythme de la fenêtre SLO ; page à 14,4, ticket à 6)")
d.ts("Burn rate sur 1 h", "Part de requêtes mauvaises / budget d'erreur, fenêtre 1 h. Au-dessus de 14,4 (et 5 min confirmé) : page.",
     [("slo:burn_rate:1h", "{{class}} / {{sli}}")], "short", w=12)
d.ts("Burn rate sur 5 min (confirmation)", "Fenêtre courte : évite d'alerter sur un incident déjà terminé.",
     [("slo:burn_rate:5m", "{{class}} / {{sli}}")], "short", w=12)
d.ts("Burn rate sur 6 h", "Fuite lente : au-dessus de 6 (et 30 min confirmé) : ticket.", [("slo:burn_rate:6h", "{{class}} / {{sli}}")], "short", w=12)
d.ts("Part de requêtes mauvaises (5 min)", "Le SLI brut : requêtes qui violent l'objectif (échec, TTFT ou durée trop longs).",
     [("slo:error_ratio:rate5m", "{{class}} / {{sli}}")], "percentunit", w=12)
d.row("Budget d'erreur consommé sur la période affichée")
for c in ("interactive", "rag", "multiturn", "batch"):
    d.stat(f"{c} : budget consommé (disponibilité)", "Moyenne des parts de requêtes en échec sur la période affichée / budget d'erreur (approximation : moyenne de ratios 5 min, non pondérée par le trafic). 100 % = budget épuisé.",
           f'avg_over_time(slo:error_ratio:rate5m{{class="{c}",sli="availability"}}[$__range]) / scalar(slo:error_budget{{class="{c}",sli="availability"}})', "percentunit", w=6,
           thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 0.5}, {"color": "red", "value": 1}])
d.row("Goodput : requêtes par seconde qui respectent l'objectif de latence, face au trafic total")
d.ts("Requêtes totales par classe", "Trafic vu par LiteLLM, par alias de clé.", [("sum by (api_key_alias) (rate(litellm_proxy_total_requests_metric_total[$__rate_interval]))", "{{api_key_alias}}")], "reqps", w=12)
d.ts("Requêtes sous l'objectif de TTFT", "Débit des requêtes dont le premier token arrive dans le seuil (interactive 5 s, multiturn 5 s, rag 10 s).",
     [('sum by (api_key_alias) (rate(litellm_llm_api_time_to_first_token_metric_bucket{api_key_alias=~"lab-interactive|lab-multiturn",le="5.0"}[$__rate_interval]))', "{{api_key_alias}} <= 5 s"),
      ('sum by (api_key_alias) (rate(litellm_llm_api_time_to_first_token_metric_bucket{api_key_alias="lab-rag",le="10.0"}[$__rate_interval]))', "{{api_key_alias}} <= 10 s")], "reqps", w=12)
d.ts("Latence de bout en bout par classe (p95)", "p95 vu par LiteLLM, par alias de clé.",
     [("histogram_quantile(0.95, sum by (le, api_key_alias) (rate(litellm_request_total_latency_metric_bucket[$__rate_interval])))", "{{api_key_alias}}")], "s", w=12)
d.ts("TTFT par classe (p95)", "p95 du premier token vu par LiteLLM (streaming), par alias de clé.",
     [("histogram_quantile(0.95, sum by (le, api_key_alias) (rate(litellm_llm_api_time_to_first_token_metric_bucket[$__rate_interval])))", "{{api_key_alias}}")], "s", w=12)
d.save(vars_model=False)

# ---------------- 07 Santé du GPU ----------------
d = D("lab-gpu-health", "07 - Santé du GPU", "Lab", "Le GPU est-il en bonne santé ? Température, puissance, horloges, bridage décodé, erreurs mémoire et XID, services GPU. Mode d'emploi : docs/gpu/03-dashboards.md.")
d.row("Santé en un coup d'œil (tout doit être vert)")
d.stat("GPU vus par DCGM", "Nombre de GPU mesurés par DCGM. Doit égaler le nombre de GPU annoncés par Kubernetes (panneau suivant).", "lab:gpu_visible", "short", w=4)
d.stat("GPU annoncés par Kubernetes", "nvidia.com/gpu allouable : ce que le plugin du GPU Operator déclare. Un écart avec le panneau précédent déclenche LabGPUMissing.", "lab:gpu_allocatable", "short", w=4)
red1 = [{"color": "green", "value": None}, {"color": "red", "value": 1}]
d.stat("Dernier code XID", "0 = aucune erreur XID. Un code non nul : voir le runbook LabGPUXidError et docs/gpu/04-diagnostic-et-optimisation.md.", "max(DCGM_FI_DEV_XID_ERRORS) or vector(0)", "short", w=4, thresholds=red1)
d.stat("Erreurs ECC doubles", "Erreur mémoire non corrigeable depuis le dernier chargement du pilote. Doit rester à 0 (alerte critique LabGPUEccUncorrectable).", "max(DCGM_FI_DEV_ECC_DBE_VOL_TOTAL) or vector(0)", "short", w=4, thresholds=red1)
d.stat("Bridage matériel / thermique", "1 si le GPU ralentit pour une cause matérielle ou thermique (bits 0x8, 0x20, 0x40, 0x80 du masque). Le plafond de puissance logiciel (0x4) est normal et n'est pas compté ici.", "max(lab:gpu_throttle_hw_slowdown) or vector(0)", "short", w=4, thresholds=red1)
d.stat("Marge thermique (°C)", "Limite de fonctionnement (réglage gpuLimits, à confirmer avec nvidia-smi -q) moins la température. Orange sous 8 degrés, rouge sous 3.", "min(lab:gpu_thermal_headroom_celsius)", "celsius", w=4,
       thresholds=[{"color": "red", "value": None}, {"color": "orange", "value": 3}, {"color": "green", "value": 8}])
d.row("Thermique et puissance")
d.ts("Température et limite", "Température du GPU face à la limite de fonctionnement. Un T4 est refroidi passivement par le châssis du fournisseur : on ne peut pas agir sur le refroidissement.",
     [("DCGM_FI_DEV_GPU_TEMP", "température {{gpu}} {{Hostname}}"), ("vector(" + "85" + ")", "limite de fonctionnement (à confirmer)")], "celsius", w=8)
d.ts("Puissance et limite", "Puissance mesurée face au plafond du T4 (70 W). Près du plafond, le GPU baisse ses horloges pour rester dans l'enveloppe.",
     [("DCGM_FI_DEV_POWER_USAGE", "puissance {{gpu}} {{Hostname}}"), ("vector(70)", "limite (fiche NVIDIA)")], "watt", w=8)
d.ts("Marge de puissance et marge thermique", "Combien il reste avant le plafond de puissance (W) et avant la limite thermique (°C). Deux unités : à lire séparément.",
     [("lab:gpu_power_headroom_watts", "marge puissance (W) {{gpu}}"), ("lab:gpu_thermal_headroom_celsius", "marge thermique (°C) {{gpu}}")], "short", w=8)
d.row("Horloges et bridage")
d.ts("Horloge des unités de calcul (SM) et de la mémoire", "L'horloge monte en charge et redescend au repos. Au repos : environ 585 MHz (observé). Maximum : 1590 MHz pour les SM, 5001 MHz pour la mémoire (relevé du forum NVIDIA, à confirmer).",
     [("DCGM_FI_DEV_SM_CLOCK", "SM {{gpu}} {{Hostname}}"), ("DCGM_FI_DEV_MEM_CLOCK", "mémoire {{gpu}} {{Hostname}}")], "short", w=8)
d.ts("Horloge SM rapportée au maximum", "1 = horloge maximale. Une charge forte avec un rapport bas et une puissance proche de 70 W indique un GPU limité par sa puissance (docs/gpu/01-signaux-du-gpu.md).",
     [("lab:gpu_clock_ratio", "{{gpu}} {{Hostname}}")], "percentunit", w=8, minv=0, maxv=1)
d.ts("Bridage décodé (0 ou 1)", "Le masque DCGM_FI_DEV_CLOCK_THROTTLE_REASONS décodé : plafond de puissance logiciel (0x4, normal sous forte charge) et ralentissement matériel ou thermique (0x8, 0x20, 0x40, 0x80, anormal).",
     [("lab:gpu_throttle_sw_power_cap", "plafond de puissance logiciel (normal) {{gpu}}"), ("lab:gpu_throttle_hw_slowdown", "ralentissement matériel ou thermique (anormal) {{gpu}}")], "short", w=8, minv=0, maxv=1)
d.ts("Temps de bridage (compteurs de durée)", "Vitesse d'augmentation des compteurs de durée de bridage par puissance et par température. L'unité (ns ou µs) reste à vérifier sur le cluster : lire la forme de la courbe, pas la valeur.",
     [("rate(DCGM_FI_DEV_POWER_VIOLATION[$__rate_interval])", "puissance {{gpu}}"), ("rate(DCGM_FI_DEV_THERMAL_VIOLATION[$__rate_interval])", "thermique {{gpu}}")], "short", w=8)
d.row("Erreurs mémoire, XID et PCIe (tout doit rester à zéro)")
d.ts("Erreurs ECC", "SBE = erreur simple, corrigée (peu grave si rare) ; DBE = erreur double, non corrigeable (grave). VOL = depuis le chargement du pilote ; AGG = cumul à vie.",
     [("DCGM_FI_DEV_ECC_SBE_VOL_TOTAL", "SBE (volatile) {{gpu}}"), ("DCGM_FI_DEV_ECC_DBE_VOL_TOTAL", "DBE (volatile) {{gpu}}"), ("DCGM_FI_DEV_ECC_SBE_AGG_TOTAL", "SBE (à vie) {{gpu}}"), ("DCGM_FI_DEV_ECC_DBE_AGG_TOTAL", "DBE (à vie) {{gpu}}")], "short", w=8)
d.ts("Pages mémoire retirées", "Sur T4 (avant l'A100) une page défaillante est retirée définitivement ; « en attente » = retrait au prochain redémarrage (alerte LabGPUPageRetirementPending).",
     [("DCGM_FI_DEV_RETIRED_SBE", "retirées (erreurs simples) {{gpu}}"), ("DCGM_FI_DEV_RETIRED_DBE", "retirées (erreurs doubles) {{gpu}}"), ("DCGM_FI_DEV_RETIRED_PENDING", "en attente {{gpu}}")], "short", w=8)
d.ts("XID et rejeux PCIe", "XID = code d'erreur NVIDIA (dernier code vu). Rejeux PCIe = transferts à refaire : lien instable.",
     [("DCGM_FI_DEV_XID_ERRORS", "XID {{gpu}}"), ("increase(DCGM_FI_DEV_PCIE_REPLAY_COUNTER[$__rate_interval])", "rejeux PCIe {{gpu}}")], "short", w=8)
d.row("Services GPU dans Kubernetes")
d.ts("DaemonSets du GPU Operator : prêts / souhaités", "Le plugin qui annonce le GPU, l'exporteur de mesures et le pilote doivent être prêts sur chaque nœud GPU.",
     [('kube_daemonset_status_number_ready{namespace="gpu-operator",daemonset=~"nvidia-device-plugin-daemonset|nvidia-dcgm-exporter|nvidia-driver-daemonset"}', "prêts {{daemonset}}"),
      ('kube_daemonset_status_desired_number_scheduled{namespace="gpu-operator",daemonset=~"nvidia-device-plugin-daemonset|nvidia-dcgm-exporter|nvidia-driver-daemonset"}', "souhaités {{daemonset}}")], "short", w=12)
d.ts("Mesures GPU présentes (cible Prometheus)", "1 = l'exporteur DCGM répond. 0 ou absent : plus de mesures GPU (alerte LabScrapeTargetMissing).",
     [('up{job=~".*dcgm.*"}', "{{job}} {{instance}}")], "short", w=12, minv=0, maxv=1)
d.save(vars_model=False)

# ---------------- 08 Efficacité et goulot du GPU ----------------
d = D("lab-gpu-efficiency", "08 - Efficacité et goulot du GPU", "Lab", "Le GPU est-il bien utilisé, saturé, efficace en énergie ? Méthode USE (utilisation, saturation, erreurs), MFU et MBU, énergie par token, coût d'inactivité, comparaison des GPU. Mode d'emploi : docs/gpu/03-dashboards.md.")
d.row("Utilisation : quelles ressources du GPU travaillent ?")
d.ts("Calcul : unités actives et tensor cores", "SM_ACTIVE : part du temps où des unités de calcul travaillent (0,8 et plus est nécessaire mais pas suffisant, doc DCGM). TENSOR : tensor cores. GR_ENGINE : moteur graphique. Ne pas confondre avec GPU_UTIL.",
     [("DCGM_FI_PROF_SM_ACTIVE", "SM_ACTIVE {{gpu}}"), ("DCGM_FI_PROF_PIPE_TENSOR_ACTIVE", "TENSOR {{gpu}}"), ("DCGM_FI_PROF_GR_ENGINE_ACTIVE", "GR_ENGINE {{gpu}}")], "percentunit", w=8, minv=0, maxv=1)
d.ts("Mémoire : bande passante utilisée / maximum pratique", "DRAM_ACTIVE rapportée à 0,8, le maximum atteignable d'après la doc DCGM. Proche de 1 = le décodage est au bout de la bande passante du T4.",
     [("lab:gpu_dram_active_vs_practical_max", "{{gpu}}")], "percentunit", w=8, minv=0, maxv=1.2)
d.ts("Mémoire : VRAM utilisée", "Poids du modèle + cache KV + activations. vLLM préalloue la quasi-totalité avec gpu-memory-utilization 0,90 : une VRAM pleine ne signifie rien en soi.",
     [("DCGM_FI_DEV_FB_USED / (DCGM_FI_DEV_FB_USED + DCGM_FI_DEV_FB_FREE)", "{{gpu}}")], "percentunit", w=8, minv=0, maxv=1)
d.row("Saturation : y a-t-il de la file ?")
d.ts("File d'attente et batch", "waiting > 0 de façon durable = la capacité est dépassée. running = taille du batch (plus il est grand, plus on passe de « limité par la mémoire » à « limité par le calcul »).",
     [("lab:requests_waiting", "en attente {{model_name}}"), ("lab:requests_running", "en cours {{model_name}}")], "short", w=8)
d.ts("Cache KV et préemptions", "KV proche de 100 % puis préemptions = mémoire de contexte insuffisante : le GPU est saturé en mémoire, pas en calcul.",
     [("lab:kv_cache_usage:max", "KV {{model_name}}"), ("lab:preemptions:rate5m", "préemptions/s {{model_name}}")], "short", w=8)
d.ts("Part du temps de requête passée en prefill", "Part du temps total des requêtes (prefill + decode) passée à lire le prompt. Haut = charge de type RAG (calcul) ; bas = charge de type chat (mémoire).",
     [("sum(rate(vllm:request_prefill_time_seconds_sum[$__rate_interval])) / (sum(rate(vllm:request_prefill_time_seconds_sum[$__rate_interval])) + sum(rate(vllm:request_decode_time_seconds_sum[$__rate_interval])))", "part prefill")],
     "percentunit", w=8, minv=0, maxv=1)
d.row("MFU et MBU (estimations de vLLM, scénario gpu-health : --enable-mfu-metrics)")
d.ts("MFU : part du calcul maximal utilisée", "Opérations estimées par vLLM / 65 TFLOPS du T4. Faible en décodage (limité par la mémoire) : c'est normal.", [("lab:gpu_mfu", "MFU")], "percentunit", w=8, minv=0)
d.ts("MBU : part de la bande passante utilisée", "Octets lus et écrits estimés par vLLM / 320 Go/s. C'est le bon indicateur d'efficacité du décodage (mesuré à ≈ 83 % à 1 requête, docs/gpu/01-signaux-du-gpu.md).", [("lab:gpu_mbu", "MBU")], "percentunit", w=8, minv=0)
d.ts("Comparer MBU estimé et DRAM_ACTIVE", "Deux mesures indépendantes de la mémoire : l'estimation de vLLM et le compteur matériel. Elles doivent évoluer ensemble ; un écart durable signale une estimation à corriger.",
     [("lab:gpu_mbu", "MBU (vLLM)"), ("lab:gpu_dram_active_vs_practical_max", "DRAM_ACTIVE / 0,8 (DCGM)")], "percentunit", w=8, minv=0)
d.row("Énergie et coût")
d.ts("Débit de tokens", "Tokens de sortie générés par seconde. À lire avec la puissance du graphique voisin (unités différentes, donc deux graphiques).", [("lab:generation_tokens:rate1m", "tokens/s {{model_name}}")], "short", w=6)
d.ts("Puissance du GPU", "Watts mesurés (plafond 70 W).", [("DCGM_FI_DEV_POWER_USAGE", "{{gpu}}")], "watt", w=6)
d.ts("Tokens par joule et kWh par million de tokens", "Efficacité énergétique : plus de tokens par joule = moins d'énergie par token. Observé : le 1,5B passe de 4,2 à 15,6 tokens/J entre une charge interactive et une charge saturée.",
     [("lab:tokens_per_joule", "tokens/joule"), ("lab:gpu_kwh_per_million_tokens", "kWh par million de tokens")], "short", w=6)
d.ts("Énergie par requête (J)", "Watts moyens divisés par les requêtes servies par seconde.", [("lab:gpu_energy_per_request_joules", "joules par requête")], "short", w=6)
d.ts("Coût par million de tokens et coût d'inactivité", "Coût du GPU rapporté aux tokens, et coût par heure des GPU alloués mais inutilisés.", [("lab:cost_per_million_tokens_usd", "$ par million de tokens"), ("lab:gpu_idle_cost_usd_per_hour", "$/h de GPU inactif")], "currencyUSD", w=12)
d.ts("GPU alloués, utilisés, inactifs", "Alloué sans être utilisé = argent dépensé sans service (alerte LabGPUIdleCost).", [("lab:gpu_allocated", "alloués"), ("lab:gpu_used", "utilisés"), ("lab:gpu_allocated_idle", "alloués et inactifs")], "short", w=12)
d.row("Comparer les GPU entre eux (2 nœuds)")
d.ts("Température, puissance et horloge par GPU", "Deux GPU sous la même charge doivent se ressembler. Un GPU nettement plus chaud ou plus lent que l'autre est un candidat au remplacement.",
     [("DCGM_FI_DEV_GPU_TEMP", "température (°C) {{gpu}} {{Hostname}}"), ("DCGM_FI_DEV_POWER_USAGE", "puissance (W) {{gpu}} {{Hostname}}")], "short", w=8)
d.ts("Écart de température entre GPU", "Température maximale moins minimale. Un écart durable de plus de quelques degrés sous charge égale est suspect.", [("lab:gpu_temp_spread_celsius", "écart")], "celsius", w=8)
d.ts("Énergie par token et par pod", "Watts du GPU divisés par les tokens générés par le pod qui l'utilise (jointure DCGM / vLLM par le label pod). Deux réplicas identiques doivent avoir des valeurs proches.",
     [('max by (pod) (DCGM_FI_DEV_POWER_USAGE{pod!=""}) / sum by (pod) (rate(vllm:generation_tokens_total[$__rate_interval]))', "joules par token {{pod}}")], "short", w=8)
d.save(vars_model=False)

print("ok", sorted(str(p.relative_to(OUT)) for p in OUT.rglob("*.json")))
