# LabGPUMemoryHigh

**Symptôme.** La mémoire du GPU approche de la limite : risque d'OOM CUDA.

<!-- mots: alerte, runbook -->
> **Mots à connaître**
> - **Alerte / runbook** : Notification d'un problème / fiche qui dit quoi vérifier et quoi faire (`docs/runbooks/`).
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- Dashboard 02 : mémoire par pod.

## Leviers d'optimisation

- Réduire `gpu-memory-utilization` ou `max-model-len`.
- Scénario gpu-sharing : revoir la répartition des parts.
