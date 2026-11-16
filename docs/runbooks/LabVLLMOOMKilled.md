# LabVLLMOOMKilled

**Symptôme.** Un conteneur a été tué par le noyau (mémoire hôte).

## Vérifications

- `kubectl describe pod` : limits mémoire, allocatable du nœud.

## Leviers d'optimisation

- Relever `limits.memory` (28 Gio par nœud T4, ~24 allouables).
- Réduire `max-model-len` / `max-num-seqs`.
