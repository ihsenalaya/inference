# LabPreemptions

**Symptôme.** vLLM évince des requêtes faute de place dans le cache KV.

## Vérifications

- `vllm:num_preemptions_total`, usage du cache KV.

## Leviers d'optimisation

- Mêmes leviers que LabKVCacheSaturated.
- Limiter la concurrence côté LiteLLM (rpm/tpm de l'équipe).
