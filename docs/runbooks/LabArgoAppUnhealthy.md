# LabArgoAppUnhealthy

**Symptôme.** Une application Argo CD est dégradée ou désynchronisée.

## Vérifications

- `lab.sh status`, UI Argo CD (`lab.sh ui`), `kubectl -n argocd get app <nom> -o yaml`.

## Leviers d'optimisation

- Ordre des vagues, CRD manquantes, ressources refusées (ServerSideApply).
- Self-heal corrige les modifications manuelles.
