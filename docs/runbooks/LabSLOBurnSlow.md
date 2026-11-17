# LabSLOBurnSlow

**Symptôme.** Fuite lente du budget d'erreur : 5 % du budget part en 6 h (burn rate > 6x, confirmé sur 30 min).

## Vérifications

- Même lecture que LabSLOBurnFast, sur une durée plus longue : la dégradation est modérée mais continue.

## Leviers d'optimisation

- Ouvrir un ticket : tendance (charge qui monte, régression de configuration récente dans Git).
- Comparer avec le dernier run de référence du même profil (docs/BASELINE.md).
