# LabQueueTimeHigh

**Symptôme.** Le temps passé en file avant prefill (p95) est élevé.

<!-- mots: cache kv, keda, epp -->
> **Mots à connaître**
> - **Cache KV** : Mémoire où le modèle garde ce qu'il a déjà « compris » du texte, pour ne pas le refaire à chaque token. Il vit dans la mémoire du GPU.
> - **KEDA** : Ajoute ou retire des pods selon la file d'attente de vLLM.
> - **llm-d / EPP** : *Endpoint Picker* : choisit le pod vLLM le mieux placé (peu chargé, cache de préfixes) pour chaque requête.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- Dashboard 00 ligne 2 : requêtes en attente, usage du cache KV.

## Leviers d'optimisation

- Plus de capacité : réplicas, KEDA (seuil du trigger).
- `max-num-seqs` plus grand si le cache KV le permet.
- Routage EPP : charge par pod (dashboard 00 ligne 5).
