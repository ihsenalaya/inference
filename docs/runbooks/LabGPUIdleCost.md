# LabGPUIdleCost

**Symptôme.** Un nœud GPU allumé est inactif depuis plus de 30 minutes : il coûte sans servir.

<!-- mots: alerte, runbook -->
> **Mots à connaître**
> - **Alerte / runbook** : Notification d'un problème / fiche qui dit quoi vérifier et quoi faire (`docs/runbooks/`).
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- Dashboard 03 : part d'inactivité, coût horaire.

## Leviers d'optimisation

- `lab.sh stop` (désalloue le cluster) ou `lab.sh gpu-scale 0`.
- Au bout du lab : `lab.sh down`.
