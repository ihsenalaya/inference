#!/usr/bin/env python3
"""Critère 6 : aucun panneau vide. Évalue chaque requête PromQL des dashboards Lab sur la dernière heure.
Usage : tests/check_panels.py [url Prometheus] [fenêtre en minutes]"""
import glob, json, re, sys, time, urllib.parse, urllib.request
URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:19090"
WIN = int(sys.argv[2]) if len(sys.argv) > 2 else 60
SUB = {"$__rate_interval": "5m", "$model": ".*", "$pod": ".*", "$namespace": ".*", "${model}": ".*", "$__interval": "1m", "$__range": "1h"}
empty, ok, skipped = [], 0, 0
for f in sorted(glob.glob("gitops/observability/config/dashboards/Lab/*.json")):
    d = json.load(open(f))
    for p in d["panels"]:
        if p.get("type") == "row":
            continue
        if p.get("datasource", {}).get("type") != "prometheus":
            skipped += 1
            continue
        has = False
        for t in p.get("targets", []):
            e = t["expr"]
            for k, v in SUB.items():
                e = e.replace(k, v)
            q = urllib.parse.urlencode({"query": e, "start": time.time() - WIN * 60, "end": time.time(), "step": 60})
            try:
                r = json.load(urllib.request.urlopen(f"{URL}/api/v1/query_range?{q}", timeout=60))
                if r["data"]["result"]:
                    has = True
            except Exception as ex:  # requête invalide
                print("ERREUR", d["title"], p["title"], str(ex)[:80])
        (ok := ok + 1) if has else empty.append(f"{d['title']} / {p['title']}")
print(f"{ok} panneaux avec données, {len(empty)} vides, {skipped} non-Prometheus ignorés")
for e in empty:
    print("  VIDE :", e)
sys.exit(1 if empty else 0)
