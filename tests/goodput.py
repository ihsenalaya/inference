#!/usr/bin/env python3
"""Goodput côté client : requêtes (et tokens) qui respectent le SLO de leur classe, sur la fenêtre de mesure d'un run.

Usage : tests/goodput.py <classe> <dossier results> [...]     classe : interactive | rag | multiturn | batch
Lit <dossier>/requests.csv (produit par le job de bench avec PER_REQUEST=true) et config.yaml (durée des stages : le premier
stage est l'échauffement s'il y en a deux). Les seuils viennent de gitops/observability/config/values.yaml (bloc slo) : un
SEUL endroit pour les définir. Une requête est « bonne » si elle n'a pas échoué ET TTFT <= seuil ET durée <= seuil (quand
la classe les définit). Écrit <dossier>/goodput.json et imprime une ligne de tableau Markdown."""
import csv, json, pathlib, re, statistics as st, sys
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
SLO = yaml.safe_load((ROOT / "gitops/observability/config/values.yaml").read_text())["slo"]["classes"]


def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(round(p * (len(v) - 1))))] if v else None


def run(cls, d):
    d = pathlib.Path(d)
    slo = SLO[cls]
    rows = list(csv.DictReader(open(d / "requests.csv")))
    durs = [int(x) for x in re.findall(r"duration:\s*(\d+)", (d / "config.yaml").read_text())]
    meas = durs[-1]
    # fenêtre de mesure = les `meas` dernières secondes d'envoi (le stage de mesure est le dernier) : plus fiable que de partir du
    # premier envoi, car le client peut mettre quelques secondes à démarrer son premier stage
    hi = max(float(r["start"]) for r in rows) + 1e-6
    lo = hi - meas
    sel = [r for r in rows if lo <= float(r["start"]) < hi]
    ttft_max = float(slo["ttft"]["le"]) if "ttft" in slo else None
    e2e_max = float(slo["e2e"]["le"]) if "e2e" in slo else None
    good, bad_err, bad_ttft, bad_e2e, tok_good, tok_all = 0, 0, 0, 0, 0, 0
    ttfts, tpots, e2es = [], [], []
    for r in sel:
        e2e = float(r["end"]) - float(r["start"])
        out = int(float(r["output_tokens"] or 0))
        tok_all += out
        if r["error"] == "1":
            bad_err += 1
            continue
        ttft = float(r["ttft"]) if r["ttft"] != "" else None
        if ttft is not None:
            ttfts.append(ttft)
        if r["tpot"] != "":
            tpots.append(float(r["tpot"]))
        e2es.append(e2e)
        ok = True
        if ttft_max is not None and (ttft is None or ttft > ttft_max):
            bad_ttft += 1; ok = False
        if e2e_max is not None and e2e > e2e_max:
            bad_e2e += 1; ok = False
        if ok:
            good += 1; tok_good += out
    n = len(sel)
    o = {"run": d.name, "class": cls, "window_s": meas, "requests": n, "errors": bad_err, "good": good,
         "good_ratio": round(good / n, 4) if n else None, "bad_ttft": bad_ttft, "bad_e2e": bad_e2e,
         "goodput_req_s": round(good / meas, 3), "goodput_tok_s": round(tok_good / meas, 1), "raw_tok_s": round(tok_all / meas, 1),
         "ttft_p50": pct(ttfts, .5), "ttft_p95": pct(ttfts, .95), "tpot_p50": pct(tpots, .5), "tpot_p95": pct(tpots, .95),
         "e2e_p50": pct(e2es, .5), "e2e_p95": pct(e2es, .95),
         "slo": {"ttft_le": ttft_max, "e2e_le": e2e_max, "ttft_objective": slo.get("ttft", {}).get("objective"), "e2e_objective": slo.get("e2e", {}).get("objective"),
                 "availability": slo["availability"]}}
    (d / "goodput.json").write_text(json.dumps(o, indent=1))
    return o


if __name__ == "__main__":
    cls = sys.argv[1]
    print("| run | classe | requêtes | échecs | bonnes | part bonne | goodput req/s | goodput tok/s | tok/s brut | TTFT p50 | TTFT p95 | TPOT p50 | e2e p95 |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    f = lambda x: "n/a" if x is None else f"{x:.3g}"
    for d in sys.argv[2:]:
        o = run(cls, d)
        print(f"| {o['run']} | {cls} | {o['requests']} | {o['errors']} | {o['good']} | {f(o['good_ratio'])} | {o['goodput_req_s']} | {o['goodput_tok_s']} | {o['raw_tok_s']} | "
              f"{f(o['ttft_p50'])} | {f(o['ttft_p95'])} | {f(o['tpot_p50'])} | {f(o['e2e_p95'])} |")
