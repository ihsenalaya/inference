#!/usr/bin/env python3
"""Génère docs/METRIQUES.md depuis les /metrics réels (API metadata de Prometheus). Usage : tests/gen_metrics_catalog.py <url Prometheus>"""
import json, pathlib, sys, urllib.request
URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:19090"
LEVER = {
 "vllm:time_to_first_token_seconds": "prefill : max-num-batched-tokens, cache de préfixes, backend d'attention",
 "vllm:inter_token_latency_seconds": "decode : max-num-seqs, quantization, bande passante mémoire",
 "vllm:e2e_request_latency_seconds": "durée totale : longueur de génération, file, réplicas",
 "vllm:request_queue_time_seconds": "capacité : réplicas, KEDA, max-num-seqs",
 "vllm:request_prefill_time_seconds": "prompt long : prefill chunké, cache de préfixes",
 "vllm:request_decode_time_seconds": "decode : taille du batch, quantization",
 "vllm:num_requests_running": "taille du batch courant : max-num-seqs",
 "vllm:num_requests_waiting": "signal KEDA ; capacité",
 "vllm:kv_cache_usage_perc": "max-model-len, gpu-memory-utilization, quantization",
 "vllm:num_preemptions_total": "mémoire KV insuffisante",
 "vllm:prefix_cache_hits_total": "poids des scorers EPP, prompts à préfixe commun",
 "vllm:prefix_cache_queries_total": "idem (dénominateur du taux de hit)",
 "vllm:prompt_tokens_total": "charge de prefill", "vllm:generation_tokens_total": "débit de decode",
 "DCGM_FI_DEV_GPU_UTIL": "utilisation apparente (pas la saturation)", "DCGM_FI_PROF_GR_ENGINE_ACTIVE": "activité réelle du moteur",
 "DCGM_FI_PROF_DRAM_ACTIVE": "limite de bande passante mémoire (decode)", "DCGM_FI_DEV_FB_USED": "poids + cache KV",
 "DCGM_FI_DEV_POWER_USAGE": "plafond de puissance du T4 (70 W)", "DCGM_FI_DEV_TOTAL_ENERGY_CONSUMPTION": "tokens par joule",
 "DCGM_FI_DEV_XID_ERRORS": "fiabilité matériel", "DCGM_FI_DEV_CLOCK_THROTTLE_REASONS": "bridage puissance/thermique",
 "litellm_overhead_latency_metric": "surcoût de LiteLLM", "litellm_proxy_failed_requests_metric_total": "taux d'erreur",
 "keda_scaler_metrics_value": "valeur du trigger d'autoscaling",
}
FAMILIES = ("vllm:", "llm_d_epp_", "inference_extension_", "inference_objective_", "litellm_", "DCGM_", "keda_", "istio_requests", "istio_request_duration", "argocd_app_info")
meta = json.load(urllib.request.urlopen(URL + "/api/v1/metadata", timeout=60))["data"]
rows = []
for name in sorted(meta):
    if name.startswith(FAMILIES):
        m = meta[name][0]
        lev = LEVER.get(name) or LEVER.get(name.rsplit("_total", 1)[0]) or ""
        rows.append(f"| `{name}` | {m['type']} | {m['help'].strip().replace('|', '/')[:140]} | {lev} |")
out = pathlib.Path(__file__).resolve().parent.parent / "docs/METRIQUES.md"
out.write_text("# Catalogue des métriques\n\nGénéré depuis les `/metrics` réels (`tests/gen_metrics_catalog.py`, API metadata de Prometheus). "
               "Les noms changent d'une version à l'autre : toujours relire ce fichier avant d'écrire une requête.\n\n"
               "| Métrique | Type | Signification | Levier d'optimisation |\n|---|---|---|---|\n" + "\n".join(rows) + "\n")
print(len(rows), "métriques")
