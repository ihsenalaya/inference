# LabGPUTemperatureHigh

**Symptôme.** La température du GPU dépasse le seuil.

<!-- mots: throttling -->
> **Mots à connaître**
> - **Throttling / limite de puissance** : Watts maximum que le GPU peut consommer : 70 W par défaut sur notre T4, réglable de 60 à 70 W (`nvidia-smi -pl`). Quand il l'atteint, le GPU baisse sa fréquence (throttling).
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- Dashboard 02 : température, puissance, throttling.

## Leviers d'optimisation

- Réduire la charge continue.
- Un T4 passif dépend du refroidissement du châssis Azure : remplacer le nœud si persistant.
