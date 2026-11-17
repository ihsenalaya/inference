# LabCorruptedRequests

**Symptôme.** vLLM détecte des NaN dans les logits : sortie corrompue.

<!-- mots: alerte, runbook -->
> **Mots à connaître**
> - **Alerte / runbook** : Notification d'un problème / fiche qui dit quoi vérifier et quoi faire (`docs/runbooks/`).
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- Modèle concerné ; test de bon sens B5 (T=0 et T=0.7).

## Leviers d'optimisation

- float16 instable (ex. Gemma 3) : changer de modèle.
- Passer en `--dtype float32` pour diagnostiquer (hors budget mémoire du T4).
