# EPPDataLayerPollErrors

**Symptôme.** L'EPP n'arrive pas à interroger une source de données : état périmé.

<!-- mots: epp -->
> **Mots à connaître**
> - **llm-d / EPP** : *Endpoint Picker* : choisit le pod vLLM le mieux placé (peu chargé, cache de préfixes) pour chaque requête.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- Logs de l'EPP.

## Leviers d'optimisation

- Réseau EPP -> pods vLLM (port 8000).
