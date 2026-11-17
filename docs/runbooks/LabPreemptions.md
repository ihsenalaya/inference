# LabPreemptions

**Symptôme.** vLLM évince des requêtes faute de place dans le cache KV.

<!-- mots: cache kv -->
> **Mots à connaître**
> - **Cache KV** : Mémoire où le modèle garde ce qu'il a déjà « compris » du texte, pour ne pas le refaire à chaque token. Il vit dans la mémoire du GPU.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- `vllm:num_preemptions_total`, usage du cache KV.

## Leviers d'optimisation

- Mêmes leviers que LabKVCacheSaturated.
- Limiter la concurrence côté LiteLLM (rpm/tpm de l'équipe).
