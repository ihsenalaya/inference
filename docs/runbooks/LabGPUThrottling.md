# LabGPUThrottling

**Symptôme.** Le GPU bride ses fréquences (puissance ou thermique).

## Vérifications

- Dashboard 02 : raisons de throttling, puissance (plafond 70 W).

## Leviers d'optimisation

- La limite de puissance du T4 est le plafond habituel : le débit maximal en dépend.
- Comparer tokens/s et tokens/joule entre scénarios.
