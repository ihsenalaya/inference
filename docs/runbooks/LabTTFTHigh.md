# LabTTFTHigh

**Symptôme.** Le délai avant le premier token (p95) dépasse le seuil.

## Vérifications

- Dashboard 00 > ligne 1 : TTFT, puis ligne 2 : file d'attente et cache KV.
- Dashboard 01 : le temps est-il dans la file (queue), le prefill ou LiteLLM/Gateway ?
- `kubectl -n inference logs <pod vLLM>` : backend d'attention retenu, préemptions.

## Leviers d'optimisation

- Prefill lent : `max-num-batched-tokens`, cache de préfixes (`--enable-prefix-caching`), longueur des prompts (`max-model-len`).
- Backend d'attention sur T4 (Triton, sans tensor cores) : tester une autre version d'image vLLM (expérience A/B de BASELINE.md).
- File d'attente : ajouter un réplica / activer KEDA.
