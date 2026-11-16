#!/usr/bin/env python3
"""Normalise les dashboards importés (llm-d v1.0.0, grafana.com 12239) : datasource réelle, uid, tags.

Les dashboards llm-d utilisent déjà les noms de métriques vLLM actuels (vllm:kv_cache_usage_perc...).
On remplace seulement le placeholder ${DS_PROMETHEUS} par l'uid de la datasource provisionnée ("prometheus").
Source : https://github.com/llm-d/llm-d/tree/v1.0.0/guides/recipes/observability/grafana/dashboards
"""
import json, pathlib, re
D = pathlib.Path(__file__).resolve().parent.parent / "gitops/observability/config/dashboards/Imported"
for f in sorted(D.glob("*.json")):
    s = f.read_text()
    s = s.replace("${DS_PROMETHEUS}", "prometheus")
    d = json.loads(s)
    d.pop("__inputs", None); d.pop("__requires", None)
    d["uid"] = d.get("uid") or f.stem
    d["id"] = None
    d["tags"] = sorted(set(d.get("tags", []) + ["imported", "lab"]))
    f.write_text(json.dumps(d, indent=1, ensure_ascii=False))
    print("ok", f.name, d["uid"])
