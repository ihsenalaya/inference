# LabSLOBurnSlow

**Symptôme.** Fuite lente du budget d'erreur : 5 % du budget part en 6 h (burn rate > 6x, confirmé sur 30 min).

<!-- mots: burn rate, budget d'erreur -->
> **Mots à connaître**
> - **Burn rate** : Vitesse de consommation du budget : 1 = on l'épuise juste à la fin de la fenêtre ; 14,4 = en ~50 h pour une fenêtre de 30 jours.
> - **Budget d'erreur** : La marge autorisée : 100 % − objectif. SLO à 95 % → 5 % de requêtes lentes tolérées.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- Même lecture que LabSLOBurnFast, sur une durée plus longue : la dégradation est modérée mais continue.

## Leviers d'optimisation

- Ouvrir un ticket : tendance (charge qui monte, régression de configuration récente dans Git).
- Comparer avec le dernier run de référence du même profil (docs/BASELINE.md).
