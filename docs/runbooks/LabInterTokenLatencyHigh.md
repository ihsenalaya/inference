# LabInterTokenLatencyHigh

**Symptôme.** La latence entre deux tokens (p95) est élevée : le decode est lent.

## Vérifications

- Dashboard 02 : activité DRAM (bande passante mémoire) et puissance du GPU.
- Taille du batch (`vllm:num_requests_running`).

## Leviers d'optimisation

- Réduire `max-num-seqs` si le batch est trop grand.
- Quantization (AWQ) : moins d'octets lus par token.
- Vérifier le throttling GPU (LabGPUThrottling).
