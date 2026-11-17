# LabArgoAppUnhealthy

**Symptôme.** Une application Argo CD est dégradée ou désynchronisée.

<!-- mots: alerte, runbook -->
> **Mots à connaître**
> - **Alerte / runbook** : Notification d'un problème / fiche qui dit quoi vérifier et quoi faire (`docs/runbooks/`).
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- `lab.sh status`, UI Argo CD (`lab.sh ui`), `kubectl -n argocd get app <nom> -o yaml`.

## Leviers d'optimisation

- Ordre des vagues, CRD manquantes, ressources refusées (ServerSideApply).
- Self-heal corrige les modifications manuelles.
