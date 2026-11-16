# LabCorruptedRequests

**Symptôme.** vLLM détecte des NaN dans les logits : sortie corrompue.

## Vérifications

- Modèle concerné ; test de bon sens B5 (T=0 et T=0.7).

## Leviers d'optimisation

- float16 instable (ex. Gemma 3) : changer de modèle.
- Passer en `--dtype float32` pour diagnostiquer (hors budget mémoire du T4).
