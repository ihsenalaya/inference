#!/usr/bin/env python3
"""Bruit de mesure : médiane, écart-type et coefficient de variation (CV) de plusieurs répétitions d'un même run.
Usage : tests/noise.py <glob des dossiers results> [...]   Utilise stage_1 (stage_0 = échauffement exclu)."""
import glob, json, statistics as st, sys
runs = [d for pat in sys.argv[1:] for d in sorted(glob.glob(pat))]
M = {"TTFT p50 (s)": ("time_to_first_token", "median"), "TTFT p95 (s)": ("time_to_first_token", "p95"), "TPOT p50 (s)": ("time_per_output_token", "median"),
     "TPOT p95 (s)": ("time_per_output_token", "p95"), "latence p95 (s)": ("request_latency", "p95")}
vals = {k: [] for k in list(M) + ["tok/s sortie", "req/s servies", "échecs"]}
for d in runs:
    f = glob.glob(f"{d}/stage_1_lifecycle_metrics.json") or glob.glob(f"{d}/stage_0_lifecycle_metrics.json")
    x = json.load(open(f[0])); s = x["successes"]; lat = s["latency"]
    for k, (a, b) in M.items():
        v = (lat.get(a) or {}).get(b)
        if v is not None: vals[k].append(v)
    vals["tok/s sortie"].append(s["throughput"]["output_tokens_per_sec"]); vals["req/s servies"].append(s["throughput"]["requests_per_sec"])
    vals["échecs"].append(x.get("failures", {}).get("count", 0))
print(f"{len(runs)} répétitions : {', '.join(d.split('/')[-1] for d in runs)}\n")
print("| Métrique | médiane | écart-type | CV (%) | min - max |\n|---|---|---|---|---|")
for k, v in vals.items():
    if len(v) >= 2:
        m = st.median(v); sd = st.stdev(v); cv = 100 * sd / (st.mean(v) or 1)
        print(f"| {k} | {m:.4g} | {sd:.3g} | {cv:.1f} | {min(v):.4g} - {max(v):.4g} |")
