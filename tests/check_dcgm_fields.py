#!/usr/bin/env python3
"""Garde-fou : chaque champ du ConfigMap `dcgm-metrics` (gitops/platform/gpu-operator/values.yaml) doit être un nom connu.
Un nom inconnu peut empêcher dcgm-exporter de démarrer, donc de perdre toutes les mesures GPU. Un nom est accepté s'il figure :
- dans tests/fixtures/dcgm-exporter-4.8.4-fields.txt (fichier officiel de la version déployée), ou
- dans la liste des champs déjà observés sur un vrai cluster (docs/METRIQUES.md, 16/11) + les 4 compteurs de profilage vus le 17/11.
Aussi : aucune virgule dans les textes d'aide (le fichier est découpé sur les virgules)."""
import pathlib, re, sys
root = pathlib.Path(__file__).resolve().parent.parent
conf = (root / "gitops/platform/gpu-operator/values.yaml").read_text()
block = conf.split("data: |-", 1)[1]
known = {l.strip() for l in (root / "tests/fixtures/dcgm-exporter-4.8.4-fields.txt").read_text().splitlines() if l.strip() and not l.startswith("#")}
known |= set(re.findall(r"`(DCGM_FI_[A-Z0-9_]+)`", (root / "docs/METRIQUES.md").read_text()))
known |= {"DCGM_FI_PROF_SM_ACTIVE", "DCGM_FI_PROF_SM_OCCUPANCY", "DCGM_FI_PROF_PIPE_TENSOR_ACTIVE", "DCGM_FI_PROF_PIPE_FP16_ACTIVE"}
bad = []
for line in block.splitlines():
    t = line.strip()
    if not t or t.startswith("#"):
        continue
    if not t.startswith("DCGM_"):
        break
    parts = t.split(",")
    if len(parts) != 3:
        bad.append(f"ligne mal formée (virgule dans l'aide ?) : {t}")
        continue
    if parts[0].strip() not in known:
        bad.append(f"champ inconnu pour dcgm-exporter 4.8.4 : {parts[0].strip()}")
print("\n".join(bad) or "champs DCGM valides")
sys.exit(1 if bad else 0)
