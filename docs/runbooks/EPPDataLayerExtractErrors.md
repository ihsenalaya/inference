# EPPDataLayerExtractErrors

**Symptôme.** Erreurs d'extraction des métriques des pods par l'EPP.

<!-- mots: epp -->
> **Mots à connaître**
> - **llm-d / EPP** : *Endpoint Picker* : choisit le pod vLLM le mieux placé (peu chargé, cache de préfixes) pour chaque requête.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- Version de vLLM / noms de métriques attendus par l'EPP.

## Leviers d'optimisation

- Aligner la version de vLLM avec celle de l'EPP.
