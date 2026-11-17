#!/usr/bin/env python3
"""Tableau Markdown « mesures par classe » à partir des goodput.json / server_window.json des runs de classe.
Usage : tests/slo_table.py <scénario> [tag]   ex. tests/slo_table.py baseline-7b   (dossiers results/*-<scénario>-<profil>-class[-tag])"""
import glob, json, pathlib, sys
scen = sys.argv[1]; tag = f"-{sys.argv[2]}" if len(sys.argv) > 2 else ""
rows = [("interactive", "interactive"), ("rag", "long-prompt"), ("multiturn", "multi-turn"), ("batch", "batch")]
print("| Classe | Run | Requêtes | Échecs | Part bonne | Objectif | Goodput req/s | Goodput tok/s | TTFT p50 / p95 (client) | TPOT p50 | Durée p95 (client) | GPU util | KV max |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for cls, prof in rows:
    for d in sorted(glob.glob(f"results/*-{scen}-{prof}-class{tag}")):
        d = pathlib.Path(d)
        if not (d / "goodput.json").exists():
            continue
        g = json.load(open(d / "goodput.json")); s = json.load(open(d / "server_window.json")) if (d / "server_window.json").exists() else {}
        obj = g["slo"].get("ttft_objective") or g["slo"].get("e2e_objective")
        ok = "oui" if g["good_ratio"] is not None and g["good_ratio"] >= obj else "**non**"
        print(f"| {cls} | `{d.name}` | {g['requests']} | {g['errors']} | {g['good_ratio']*100:.1f} % | {obj*100:.0f} % ({ok}) | {g['goodput_req_s']} | {g['goodput_tok_s']} | "
              f"{g['ttft_p50']:.3g} / {g['ttft_p95']:.3g} s | {g['tpot_p50']:.3g} s | {g['e2e_p95']:.3g} s | {s.get('gpu_util','n/a')} | {s.get('kv_usage','n/a')} |")
