# LabSLOBurnFast

**Symptôme.** Le budget d'erreur d'une classe de charge fond vite : 2 % du budget de 30 jours part en 1 h (burn rate > 14,4x, confirmé sur 5 min).

<!-- mots: ttft, cache kv, keda, burn rate, budget d'erreur, slo -->
> **Mots à connaître**
> - **TTFT** : *Time To First Token* : attente avant le premier token de la réponse. C'est ce que l'utilisateur ressent en premier.
> - **Cache KV** : Mémoire où le modèle garde ce qu'il a déjà « compris » du texte, pour ne pas le refaire à chaque token. Il vit dans la mémoire du GPU.
> - **KEDA** : Ajoute ou retire des pods selon la file d'attente de vLLM.
> - **Burn rate** : Vitesse de consommation du budget : 1 = on l'épuise juste à la fin de la fenêtre ; 14,4 = en ~50 h pour une fenêtre de 30 jours.
> - **Budget d'erreur** : La marge autorisée : 100 % − objectif. SLO à 95 % → 5 % de requêtes lentes tolérées.
> - **SLO** : Un objectif chiffré de qualité de service, par exemple « 95 % des réponses commencent en moins de 5 s ».
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Vérifications

- Dashboard « SLO par classe » : quelle classe, quel SLI (availability, ttft, e2e) ?
- `slo:burn_rate:5m` et `slo:burn_rate:1h` par classe et SLI.
- Cause côté serveur ou côté charge ? File vLLM (`lab:requests_waiting`), cache KV, surcharge (débit entrant > plateau).
- Une seule classe touchée : regarder le profil de cette classe (prompts plus longs ? débit plus haut ?).

## Leviers d'optimisation

- Surcharge : ajouter un réplica (`lab.sh gpu-scale 2`), limiter le débit de la classe (rpm/tpm LiteLLM), activer KEDA.
- Classe RAG : prefill de prompts longs, modèle plus petit ou prompts plus courts.
- Ne pas relever le seuil du SLO pour faire taire l'alerte : décider d'abord si l'objectif est le bon.
