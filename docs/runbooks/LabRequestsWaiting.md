# LabRequestsWaiting

**Symptôme.** Des requêtes attendent depuis plus de 5 min : la capacité est insuffisante.

<!-- mots: cold start, keda -->
> **Mots à connaître**
> - **Cold start** : Délai entre « on demande un GPU / un pod » et « il répond ». Ici : **721 s** pour un nœud GPU, **~3,5 min** pour changer de modèle (observé).
> - **KEDA** : Ajoute ou retire des pods selon la file d'attente de vLLM.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- `lab:requests_waiting`, KEDA (réplicas désirés/prêts), état du GPU.

## Leviers d'optimisation

- Augmenter les réplicas (`lab.sh gpu-scale 2`) ou activer le scénario `baseline-7b-keda`.
- Revoir `max-num-seqs`, `gpu-memory-utilization`.
- Un cold start de 3-4 min retarde le scale-out : pas de scale-to-zero.
