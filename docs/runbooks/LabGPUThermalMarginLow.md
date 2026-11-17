# LabGPUThermalMarginLow

**Symptôme.** La température du GPU approche de sa limite de fonctionnement : le bridage thermique approche.

<!-- mots: alerte, runbook -->
> **Mots à connaître**
> - **Alerte / runbook** : Notification d'un problème / fiche qui dit quoi vérifier et quoi faire (`docs/runbooks/`).
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- Dashboard 07 : température, marge thermique, puissance.
- `nvidia-smi -q -d TEMPERATURE` : seuils réels de ce GPU (Max Operating, Slowdown, Shutdown).

## Leviers d'optimisation

- Réduire la charge continue ou ajouter un réplica pour la répartir.
- Si la marge reste faible à charge modérée, le nœud est suspect : le comparer à l'autre GPU et le remplacer si besoin.
