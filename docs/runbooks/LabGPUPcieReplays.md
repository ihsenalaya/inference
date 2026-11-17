# LabGPUPcieReplays

**Symptôme.** Le lien PCIe entre le GPU et la machine a dû rejouer des transferts : lien instable.

<!-- mots: xid -->
> **Mots à connaître**
> - **XID** : Code d'erreur NVIDIA signalant un problème GPU (ex. 79 : GPU tombé du bus).
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- `DCGM_FI_DEV_PCIE_REPLAY_COUNTER` ; débit PCIe (`DCGM_FI_PROF_PCIE_TX_BYTES` / `RX`).

## Leviers d'optimisation

- Un rejeu isolé est bénin ; une série signale un problème matériel : vider et remplacer le nœud (risque de XID 79).
