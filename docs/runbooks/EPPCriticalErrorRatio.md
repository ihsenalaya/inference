# EPPCriticalErrorRatio

**Symptôme.** Plus de 20 % des requêtes EPP échouent : chemin d'inférence dégradé.

<!-- mots: epp -->
> **Mots à connaître**
> - **llm-d / EPP** : *Endpoint Picker* : choisit le pod vLLM le mieux placé (peu chargé, cache de préfixes) pour chaque requête.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- Idem EPPHighErrorRatio.

## Leviers d'optimisation

- Idem ; envisager un rollback du scénario.
