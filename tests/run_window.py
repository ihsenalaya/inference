#!/usr/bin/env python3
"""Signaux serveur/GPU moyens sur la fenêtre de mesure d'un run de bench (stage de mesure, bords de 15 s exclus).

Usage : tests/run_window.py <dossier results> [<dossier> ...]   (Prometheus joignable sur 127.0.0.1:19090 ;
`kubectl -n monitoring port-forward svc/kps-prometheus 19090:9090`). La fin du run vient de meta.json (date), la durée du
dernier stage de config.yaml. Écrit aussi <dossier>/server_window.json. Sortie : une ligne de tableau Markdown par run."""
import json, os, pathlib, sys, urllib.parse, urllib.request, datetime, re

PROM = "http://127.0.0.1:19090/api/v1/query"
Q = {
    "gpu_util": "avg(DCGM_FI_DEV_GPU_UTIL)",
    "gr_engine": "avg(DCGM_FI_PROF_GR_ENGINE_ACTIVE)",
    "sm_active": "avg(DCGM_FI_PROF_SM_ACTIVE)",
    "sm_occupancy": "avg(DCGM_FI_PROF_SM_OCCUPANCY)",
    "tensor": "avg(DCGM_FI_PROF_PIPE_TENSOR_ACTIVE)",
    "fp16": "avg(DCGM_FI_PROF_PIPE_FP16_ACTIVE)",
    "dram": "avg(DCGM_FI_PROF_DRAM_ACTIVE)",
    "power_w": "avg(DCGM_FI_DEV_POWER_USAGE)",
    "sm_clock_mhz": "avg(DCGM_FI_DEV_SM_CLOCK)",
    "temp_c": "avg(DCGM_FI_DEV_GPU_TEMP)",
    "running": "sum(lab:requests_running)",
    "waiting": "sum(lab:requests_waiting)",
    "kv_usage": "max(lab:kv_cache_usage:max)",
    "vllm_cpu_cores": "sum(lab:vllm_cpu_cores)",
    "temp_c_max": "max(DCGM_FI_DEV_GPU_TEMP)",
    "throttle_mask_max": "max(DCGM_FI_DEV_CLOCK_THROTTLE_REASONS)",
    "sw_power_cap_part": "avg(lab:gpu_throttle_sw_power_cap)",
    "hw_slowdown_part": "avg(lab:gpu_throttle_hw_slowdown)",
    "mbu": "lab:gpu_mbu",
    "mfu": "lab:gpu_mfu",
    "energy_j_per_req": "lab:gpu_energy_per_request_joules",
}


def query(expr, t):
    url = PROM + "?" + urllib.parse.urlencode({"query": expr, "time": t})
    r = json.load(urllib.request.urlopen(url, timeout=30))["data"]["result"]
    return float(r[0]["value"][1]) if r else None


def last_stage(cfg_text):
    durs = [int(m) for m in re.findall(r"duration:\s*(\d+)", cfg_text)]
    return durs[-1] if durs else 300


def window(d):
    d = pathlib.Path(d)
    meta = json.loads((d / "meta.json").read_text())
    end = datetime.datetime.fromisoformat(meta["date"]).timestamp()
    dur = last_stage((d / "config.yaml").read_text()) if (d / "config.yaml").exists() else 300
    # meta.date est écrit après la fin du job (+ récupération des logs) : la fin réelle du stage est un peu avant ; on retire 15 s de marge
    t_end = end - 15
    span = max(dur - 30, 30)
    out = {"run": d.name, "window_s": span}
    for k, e in Q.items():
        v = query(f"avg_over_time(({e})[{span}s:15s])" if k not in ("kv_usage",) else f"max_over_time(({e})[{span}s:15s])", t_end)
        out[k] = None if v is None else round(v, 4)
    # latences vues de trois endroits sur la MÊME fenêtre : vLLM (serveur), LiteLLM (passerelle, par classe si ALIAS est donné)
    hq = lambda q, m, sel="": query(f"histogram_quantile({q}, sum by (le) (increase({m}_bucket{sel}[{span}s])))", t_end)
    out["vllm_ttft_p50"], out["vllm_ttft_p95"] = hq(0.5, "vllm:time_to_first_token_seconds"), hq(0.95, "vllm:time_to_first_token_seconds")
    out["vllm_e2e_p95"] = hq(0.95, "vllm:e2e_request_latency_seconds")
    alias = os.environ.get("ALIAS")
    if alias:
        sel = '{api_key_alias="%s"}' % alias
        out["litellm_ttft_p50"], out["litellm_ttft_p95"] = hq(0.5, "litellm_llm_api_time_to_first_token_metric", sel), hq(0.95, "litellm_llm_api_time_to_first_token_metric", sel)
        out["litellm_e2e_p95"] = hq(0.95, "litellm_request_total_latency_metric", sel)
        out["litellm_requests"] = query(f'sum(increase(litellm_proxy_total_requests_metric_total{sel}[{span}s]))', t_end)
    for k, v in list(out.items()):
        if isinstance(v, float): out[k] = round(v, 4)
    (d / "server_window.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    cols = ["gpu_util", "gr_engine", "sm_active", "sm_occupancy", "tensor", "fp16", "dram", "power_w", "sm_clock_mhz", "kv_usage", "running", "waiting", "vllm_cpu_cores"]
    print("| run | " + " | ".join(cols) + " |\n|---|" + "---|" * len(cols))
    for d in sys.argv[1:]:
        o = window(d)
        print(f"| {o['run']} | " + " | ".join("n/a" if o[c] is None else f"{o[c]:g}" for c in cols) + " |")
