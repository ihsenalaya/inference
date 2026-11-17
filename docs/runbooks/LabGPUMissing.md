# LabGPUMissing

**Symptôme.** Kubernetes annonce un nombre de GPU différent de celui que DCGM voit : un GPU manque, ou le plugin ou l'exporteur est en panne.

<!-- mots: dcgm -->
> **Mots à connaître**
> - **DCGM** : Outil NVIDIA qui mesure le GPU ; `dcgm-exporter` publie ces mesures pour Prometheus.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- `kubectl get nodes -o custom-columns=...` (champ `nvidia.com/gpu` allouable) ; pods `nvidia-device-plugin-daemonset` et `nvidia-dcgm-exporter` dans `gpu-operator`.
- `nvidia-smi -L` depuis le pod du pilote.

## Leviers d'optimisation

- Redémarrer le DaemonSet fautif ; si `nvidia-smi` ne voit pas le GPU, le nœud est à remplacer.
