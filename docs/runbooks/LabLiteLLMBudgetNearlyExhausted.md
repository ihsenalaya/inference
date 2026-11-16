# LabLiteLLMBudgetNearlyExhausted

**Symptôme.** Le budget d'une équipe LiteLLM est presque épuisé.

## Vérifications

- Métriques `litellm_remaining_team_budget_metric`.

## Leviers d'optimisation

- Relever `max_budget` via l'API LiteLLM `/team/update`.
