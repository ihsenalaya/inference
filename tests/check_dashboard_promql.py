#!/usr/bin/env python3
"""Vérifie la SYNTAXE PromQL de toutes les requêtes des dashboards « Lab » (sans cluster) : chaque requête devient une règle d'enregistrement
temporaire contrôlée par `promtool check rules`. Cela ne prouve pas que les métriques existent (voir tests/check_panels.py sur un cluster vivant)."""
import glob, json, pathlib, subprocess, sys, tempfile
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
SUB = {"$__rate_interval": "5m", "$__range": "1h", "$__interval": "1m", "${model}": ".*", "$model": ".*", "$pod": ".*", "$namespace": ".*"}
exprs = []
for f in sorted(glob.glob(str(ROOT / "gitops/observability/config/dashboards/Lab/*.json"))):
    d = json.load(open(f))
    for p in d["panels"]:
        if p.get("type") == "row" or p.get("datasource", {}).get("type") != "prometheus":
            continue
        for t in p.get("targets", []):
            e = t["expr"]
            for k, v in SUB.items():
                e = e.replace(k, v)
            exprs.append((d["title"], p["title"], e))


def check(rules):
    with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as fh:
        yaml.safe_dump({"groups": [{"name": "dashboards", "rules": rules}]}, fh)
    r = subprocess.run(["promtool", "check", "rules", fh.name], capture_output=True, text=True)
    return r.returncode == 0, (r.stdout + r.stderr)


ok, out = check([{"record": f"dash_check_{i}", "expr": e} for i, (_, _, e) in enumerate(exprs)])
if ok:
    print(f"{len(exprs)} requêtes PromQL de dashboards : syntaxe valide")
    sys.exit(0)
bad = [(t, p, e) for t, p, e in exprs if not check([{"record": "x", "expr": e}])[0]]
for t, p, e in bad:
    print(f"SYNTAXE INVALIDE : {t} / {p}\n    {e}")
sys.exit(1)
