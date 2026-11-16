# LabGPUMemoryHigh

**Symptôme.** La mémoire du GPU approche de la limite : risque d'OOM CUDA.

## Vérifications

- Dashboard 02 : mémoire par pod.

## Leviers d'optimisation

- Réduire `gpu-memory-utilization` ou `max-model-len`.
- Scénario gpu-sharing : revoir la répartition des parts.
