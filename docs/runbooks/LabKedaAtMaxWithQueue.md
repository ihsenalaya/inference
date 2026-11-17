# LabKedaAtMaxWithQueue

**Symptôme.** KEDA est au maximum de réplicas et la file n'est pas vide.

<!-- mots: keda -->
> **Mots à connaître**
> - **KEDA** : Ajoute ou retire des pods selon la file d'attente de vLLM.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- `kubectl -n inference get scaledobject,hpa`
- Quota T4 : 2 nœuds maximum.

## Leviers d'optimisation

- Relever `maxReplicas` (et `gpu-scale`).
- Alléger le modèle ou quantizer.
- Revoir le seuil du trigger.
