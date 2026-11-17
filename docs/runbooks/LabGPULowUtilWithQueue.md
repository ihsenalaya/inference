# LabGPULowUtilWithQueue

**Symptôme.** Le GPU est peu utilisé alors que des requêtes attendent : le goulot est ailleurs.

<!-- mots: throttling -->
> **Mots à connaître**
> - **Throttling / limite de puissance** : Watts maximum que le GPU peut consommer : 70 W par défaut sur notre T4, réglable de 60 à 70 W (`nvidia-smi -pl`). Quand il l'atteint, le GPU baisse sa fréquence (throttling).
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- CPU du pod vLLM (tokenisation, scheduling), réseau, `cpu` throttling du conteneur.
- Dashboard 01 : décomposition du temps.

## Leviers d'optimisation

- Augmenter les requests/limits CPU du pod vLLM.
- Vérifier le surcoût LiteLLM / Gateway.
- `max-num-seqs`, `max-num-batched-tokens` trop bas.
