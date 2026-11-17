# LabGPUThrottling

**Symptôme.** Le GPU bride ses fréquences (puissance ou thermique).

<!-- mots: throttling -->
> **Mots à connaître**
> - **Throttling / limite de puissance** : Le GPU baisse sa fréquence quand il atteint sa limite (70 W sur T4).
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- Dashboard 02 : raisons de throttling, puissance (plafond 70 W).

## Leviers d'optimisation

- La limite de puissance du T4 est le plafond habituel : le débit maximal en dépend.
- Comparer tokens/s et tokens/joule entre scénarios.
