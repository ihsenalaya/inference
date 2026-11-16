# LabKVCacheSaturated

**Symptôme.** Le cache KV dépasse le seuil : risque de préemptions et de latence.

## Vérifications

- Dashboard 00 : usage du cache KV, préemptions.

## Leviers d'optimisation

- Réduire `max-model-len` ou `max-num-seqs`.
- Augmenter `gpu-memory-utilization` (avec prudence sur 16 Go).
- Modèle quantizé : plus de place pour le KV (le KV en FP8 n'est pas dispo sur Triton).
