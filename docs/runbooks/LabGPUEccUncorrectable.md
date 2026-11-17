# LabGPUEccUncorrectable

**Symptôme.** Le GPU a détecté une erreur mémoire double, non corrigeable : donnée potentiellement fausse, matériel suspect.

<!-- mots: xid -->
> **Mots à connaître**
> - **XID** : Code d'erreur NVIDIA signalant un problème GPU (ex. 79 : GPU tombé du bus).
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- `DCGM_FI_DEV_ECC_DBE_VOL_TOTAL` et le cumul à vie `DCGM_FI_DEV_ECC_DBE_AGG_TOTAL` ; pages retirées (`nvidia-smi -q -d PAGE_RETIREMENT`).
- Journal du noyau : XID 48, puis 63 ou 64.

## Leviers d'optimisation

- Vider le nœud (cordon + drain), le redémarrer ou le remplacer : une erreur double n'est pas à ignorer.
- Ne pas remettre le nœud en service sans diagnostic (`dcgmi diag -r 2`, vLLM arrêté).
