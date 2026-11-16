# LabGPUIdleCost

**Symptôme.** Un nœud GPU allumé est inactif depuis plus de 30 minutes : il coûte sans servir.

## Vérifications

- Dashboard 03 : part d'inactivité, coût horaire.

## Leviers d'optimisation

- `lab.sh stop` (désalloue le cluster) ou `lab.sh gpu-scale 0`.
- Au bout du lab : `lab.sh down`.
