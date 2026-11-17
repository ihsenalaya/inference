# LabGPUTemperatureHigh

**Symptôme.** La température du GPU dépasse le seuil.

<!-- mots: throttling -->
> **Mots à connaître**
> - **Throttling / limite de puissance** : Le GPU baisse sa fréquence quand il atteint sa limite (70 W sur T4).
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- Dashboard 02 : température, puissance, throttling.

## Leviers d'optimisation

- Réduire la charge continue.
- Un T4 passif dépend du refroidissement du châssis Azure : remplacer le nœud si persistant.
