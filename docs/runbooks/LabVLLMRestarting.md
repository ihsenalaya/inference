# LabVLLMRestarting

**Symptôme.** Un pod vLLM a redémarré.

## Vérifications

- `kubectl -n inference describe pod`, `logs --previous`, événements (Loki).

## Leviers d'optimisation

- OOM : réduire `gpu-memory-utilization` / mémoire hôte.
- Sonde de démarrage trop courte : `startupFailureThreshold`.
