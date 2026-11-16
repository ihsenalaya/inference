# LabErrorRateHigh

**Symptôme.** Part élevée de requêtes en échec vue par LiteLLM.

## Vérifications

- `kubectl -n gateway logs deploy/litellm`
- Logs Loki (dashboard 05) : OOM, CUDA, timeouts.
- `kubectl -n inference get llminferenceservices` : prêt ?

## Leviers d'optimisation

- Saturation : augmenter les réplicas ou réduire `max-model-len`.
- Fallback LiteLLM vers un autre modèle (scénario multi-model).
- Timeouts LiteLLM / vLLM.
