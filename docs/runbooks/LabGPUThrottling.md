# LabGPUThrottling

**Symptôme.** Le GPU ralentit ses horloges pour une cause matérielle ou thermique (pas le simple plafond de puissance logiciel, qui est normal).

<!-- mots: alerte, runbook -->
> **Mots à connaître**
> - **Alerte / runbook** : Notification d'un problème / fiche qui dit quoi vérifier et quoi faire (`docs/runbooks/`).
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- Dashboard 07 « Santé du GPU », ligne « Horloges et bridage ».
- `nvidia-smi -q -d PERFORMANCE,TEMPERATURE,POWER` depuis le pod du pilote : quelles raisons sont actives ?
- Masque `DCGM_FI_DEV_CLOCK_THROTTLE_REASONS` : 0x8 ralentissement matériel, 0x20 ralentissement thermique logiciel, 0x40 ralentissement thermique matériel, 0x80 frein de puissance matériel.

## Leviers d'optimisation

- Thermique : réduire la charge ; si cela dure, signaler le nœud et le remplacer (sur Azure, le refroidissement n'est pas à notre portée).
- Frein de puissance matériel (0x80) : cause externe à la carte (alimentation) : remplacer le nœud.
- Comparer avec l'autre GPU (dashboard 08, ligne « Comparer les GPU ») pour distinguer un nœud défaillant d'une charge trop forte.
