# LabGPUPageRetirementPending

**Symptôme.** Des pages mémoire du GPU sont marquées pour retrait : elles ne le seront qu'au prochain redémarrage (GPU avant l'A100, comme le T4).

<!-- mots: xid -->
> **Mots à connaître**
> - **XID** : Code d'erreur NVIDIA signalant un problème GPU (ex. 79 : GPU tombé du bus).
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- `nvidia-smi -q -d PAGE_RETIREMENT` : pages retirées (erreurs simples ou doubles) et en attente.
- Journal du noyau : XID 63.

## Leviers d'optimisation

- Planifier un redémarrage du nœud à un moment calme (vider d'abord).
- Si les retraits se répètent ou échouent (XID 64), remplacer le nœud.
