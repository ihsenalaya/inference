# LabVLLMOOMKilled

**Symptôme.** Un conteneur a été tué par le noyau (mémoire hôte).

<!-- mots: alerte, runbook -->
> **Mots à connaître**
> - **Alerte / runbook** : Notification d'un problème / fiche qui dit quoi vérifier et quoi faire (`docs/runbooks/`).
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- `kubectl describe pod` : limits mémoire, allocatable du nœud.

## Leviers d'optimisation

- Relever `limits.memory` (28 Gio par nœud T4, ~24 allouables).
- Réduire `max-model-len` / `max-num-seqs`.
