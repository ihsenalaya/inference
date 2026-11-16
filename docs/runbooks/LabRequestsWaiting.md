# LabRequestsWaiting

**Symptôme.** Des requêtes attendent depuis plus de 5 min : la capacité est insuffisante.

## Vérifications

- `lab:requests_waiting`, KEDA (réplicas désirés/prêts), état du GPU.

## Leviers d'optimisation

- Augmenter les réplicas (`lab.sh gpu-scale 2`) ou activer le scénario `baseline-7b-keda`.
- Revoir `max-num-seqs`, `gpu-memory-utilization`.
- Un cold start de 3-4 min retarde le scale-out : pas de scale-to-zero.
