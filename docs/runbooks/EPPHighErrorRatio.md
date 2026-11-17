# EPPHighErrorRatio

**Symptôme.** Plus de 5 % des requêtes traitées par l'EPP échouent.

<!-- mots: epp, tls -->
> **Mots à connaître**
> - **llm-d / EPP** : *Endpoint Picker* : choisit le pod vLLM le mieux placé (peu chargé, cache de préfixes) pour chaque requête.
> - **TLS / mTLS** : Chiffrement d'un échange ; en *mTLS* les deux côtés prouvent aussi leur identité.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- Logs de l'EPP : `kubectl -n inference logs deploy/<modèle>-kserve-router-scheduler`.

## Leviers d'optimisation

- TLS Gateway -> EPP (DestinationRule).
- Pods vLLM NotReady.
