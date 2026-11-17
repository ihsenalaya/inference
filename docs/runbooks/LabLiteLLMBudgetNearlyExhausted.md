# LabLiteLLMBudgetNearlyExhausted

**Symptôme.** Le budget d'une équipe LiteLLM est presque épuisé.

<!-- mots: alerte, runbook -->
> **Mots à connaître**
> - **Alerte / runbook** : Notification d'un problème / fiche qui dit quoi vérifier et quoi faire (`docs/runbooks/`).
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- Métriques `litellm_remaining_team_budget_metric`.

## Leviers d'optimisation

- Relever `max_budget` via l'API LiteLLM `/team/update`.
