# EPPExtProcStreamErrors

**Symptôme.** Les flux ext_proc Envoy <-> EPP se terminent en erreur.

<!-- mots: epp, tls -->
> **Mots à connaître**
> - **llm-d / EPP** : *Endpoint Picker* : choisit le pod vLLM le mieux placé (peu chargé, cache de préfixes) pour chaque requête.
> - **TLS / mTLS** : Chiffrement d'un échange ; en *mTLS* les deux côtés prouvent aussi leur identité.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- Logs istio-proxy de la Gateway (Loki dashboard 05).

## Leviers d'optimisation

- `DestinationRule` TLS (insecureSkipVerify) vers le service EPP.
