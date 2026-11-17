#!/usr/bin/env python3
"""Rassemble les résultats de results/*/ en tableaux Markdown pour docs/BASELINE.md.
Usage : tests/collect_baseline.py [url Prometheus]  (Prometheus sert à lire puissance GPU moyenne, énergie et cache de préfixes)"""
import datetime, glob, json, pathlib, sys, urllib.parse, urllib.request
URL = sys.argv[1] if len(sys.argv) > 1 else None
GPU_PRICE = 0.526
ROOT = pathlib.Path(__file__).resolve().parent.parent / "results"

def prom(q, t):
    if not URL: return None
    try:
        r = json.load(urllib.request.urlopen(f"{URL}/api/v1/query?{urllib.parse.urlencode({'query': q, 'time': t})}", timeout=30))
        v = r["data"]["result"]; return float(v[0]["value"][1]) if v else None
    except Exception: return None

def fmt(x, n=2):
    return "-" if x is None else (f"{x:.{n}f}" if isinstance(x, float) else str(x))

rows = []
for d in sorted(ROOT.glob("*/")):
    meta = d / "meta.json"; summ = next(iter(sorted(d.rglob("summary_lifecycle_metrics.json"))), None)
    if not meta.exists() or not summ: continue
    m = json.loads(meta.read_text()); s = json.loads(summ.read_text()); su = s.get("successes", {})
    lat = su.get("latency", {}); th = su.get("throughput", {})
    g = lambda k, q: (lat.get(k) or {}).get(q) if isinstance(lat.get(k), dict) else None
    end = datetime.datetime.fromisoformat(m["date"]).timestamp(); dur = s.get("benchmark_time_seconds", 0)
    watts = prom(f"avg_over_time(DCGM_FI_DEV_POWER_USAGE[{int(dur)}s])", end)
    hit = prom(f"sum(rate(vllm:prefix_cache_hits_total[{int(dur)}s])) / sum(rate(vllm:prefix_cache_queries_total[{int(dur)}s]))", end)
    otps = th.get("output_tokens_per_sec")
    cost = (GPU_PRICE / (otps * 3600) * 1e6) if otps else None
    tpj = (otps / watts) if (otps and watts) else None
    rows.append((m["scenario"], m["profile"], m["target"], g("time_to_first_token", "median"), g("time_to_first_token", "p95"), g("time_per_output_token", "median"),
                 g("time_per_output_token", "p95"), otps, th.get("requests_per_sec"), s.get("failures", {}).get("count", 0), cost, tpj, hit, watts, d.name))
print("| Scénario | Profil | Cible | TTFT p50 (s) | TTFT p95 (s) | TPOT p50 (s) | TPOT p95 (s) | tok/s sortie | req/s | erreurs | $/M tokens (1 T4) | tokens/J | hit cache préfixes | W moyen | run |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for r in rows:
    print("| " + " | ".join([r[0], r[1], r[2]] + [fmt(x, 3) if i < 3 else fmt(x, 2) for i, x in enumerate(r[3:14])] + [r[14]]) + " |")
