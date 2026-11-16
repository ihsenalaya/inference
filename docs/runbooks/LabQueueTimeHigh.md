# LabQueueTimeHigh

**Symptôme.** Le temps passé en file avant prefill (p95) est élevé.

## Vérifications

- Dashboard 00 ligne 2 : requêtes en attente, usage du cache KV.

## Leviers d'optimisation

- Plus de capacité : réplicas, KEDA (seuil du trigger).
- `max-num-seqs` plus grand si le cache KV le permet.
- Routage EPP : charge par pod (dashboard 00 ligne 5).
