# LabGPUXidError

**Symptôme.** Le GPU a signalé une erreur XID (code d'erreur NVIDIA : matériel, pilote ou application).

<!-- mots: xid, dcgm -->
> **Mots à connaître**
> - **XID** : Code d'erreur NVIDIA signalant un problème GPU (ex. 79 : GPU tombé du bus).
> - **DCGM** : Outil NVIDIA qui mesure le GPU ; `dcgm-exporter` publie ces mesures pour Prometheus.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- Lire le code : métrique `DCGM_FI_DEV_XID_ERRORS` (dernier code vu) et journal du noyau du nœud (lignes `NVRM: Xid`).
- Table officielle NVIDIA : https://docs.nvidia.com/deploy/xid-errors/ ; résumé : docs/gpu/04-diagnostic-et-optimisation.md.
- `nvidia-smi -q` (ECC, pages retirées) depuis le pod `nvidia-driver-daemonset`.
- `dcgmi health -c` depuis le pod `nvidia-dcgm` (DCGM autonome) : il décrit la panne (testé le 17/11/2026 avec un XID 79 injecté : « GPU 0 has fallen off the bus »). **`dcgmi diag -r 1` ne détecte pas un XID** : ne pas s'y fier seul.

## Leviers d'optimisation

- XID 13, 31, 43, 45 : le plus souvent une faute de l'application : redémarrer le pod vLLM ; si cela se répète sur le même GPU, diagnostic matériel (`dcgmi diag`).
- XID 48 (erreur ECC double) : si 63 ou 64 suit, vider le nœud puis réinitialiser. Sur une VM le reset du GPU est souvent impossible : redémarrer ou remplacer le nœud.
- XID 79 (GPU tombé du bus PCIe) : vider et remplacer le nœud, contacter le support.
- XID 94 : redémarrer l'application touchée ; XID 95 : réinitialiser le GPU avant de relancer ; XID 119 et 120 (GSP) : redémarrer le nœud.
