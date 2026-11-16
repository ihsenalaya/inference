# LabLiteLLMDown

**Symptôme.** Le déploiement LiteLLM n'a pas de réplica disponible.

## Vérifications

- `kubectl -n gateway describe deploy/litellm`, logs, PostgreSQL.

## Leviers d'optimisation

- Secret `litellm-secrets` / base PostgreSQL.
- Mémoire (limit 1,25 Gio).
