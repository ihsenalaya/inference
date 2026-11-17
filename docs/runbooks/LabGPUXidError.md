# LabGPUXidError

**Symptôme.** Le GPU a signalé une erreur XID (matériel, driver ou application).

<!-- mots: xid -->
> **Mots à connaître**
> - **XID** : Code d'erreur NVIDIA signalant un problème GPU (ex. 79 : GPU tombé du bus).
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- `nvidia-smi -q | grep -i xid` dans le pod GPU Operator ; `dmesg` du nœud.
- Code XID : https://docs.nvidia.com/deploy/xid-errors/

## Leviers d'optimisation

- XID 31/43 : erreur applicative (mémoire) -> réduire `gpu-memory-utilization`.
- XID 79/74 : matériel -> remplacer le nœud (`gpu-scale 0` puis `1`).
