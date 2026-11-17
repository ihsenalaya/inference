# LabVLLMRestarting

**Symptôme.** Un pod vLLM a redémarré.

<!-- mots: alerte, runbook -->
> **Mots à connaître**
> - **Alerte / runbook** : Notification d'un problème / fiche qui dit quoi vérifier et quoi faire (`docs/runbooks/`).
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- `kubectl -n inference describe pod`, `logs --previous`, événements (Loki).

## Leviers d'optimisation

- OOM : réduire `gpu-memory-utilization` / mémoire hôte.
- Sonde de démarrage trop courte : `startupFailureThreshold`.
