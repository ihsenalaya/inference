# LabLiteLLMDown

**Symptôme.** Le déploiement LiteLLM n'a pas de réplica disponible.

<!-- mots: alerte, runbook -->
> **Mots à connaître**
> - **Alerte / runbook** : Notification d'un problème / fiche qui dit quoi vérifier et quoi faire (`docs/runbooks/`).
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- `kubectl -n gateway describe deploy/litellm`, logs, PostgreSQL.

## Leviers d'optimisation

- Secret `litellm-secrets` / base PostgreSQL.
- Mémoire (limit 1,25 Gio).
