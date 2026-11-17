# LabSLOBurnFast

**Symptôme.** Le budget d'erreur d'une classe de charge fond vite : 2 % du budget de 30 jours part en 1 h (burn rate > 14,4x, confirmé sur 5 min).

## Vérifications

- Dashboard « SLO par classe » : quelle classe, quel SLI (availability, ttft, e2e) ?
- `slo:burn_rate:5m` et `slo:burn_rate:1h` par classe et SLI.
- Cause côté serveur ou côté charge ? File vLLM (`lab:requests_waiting`), cache KV, surcharge (débit entrant > plateau).
- Une seule classe touchée : regarder le profil de cette classe (prompts plus longs ? débit plus haut ?).

## Leviers d'optimisation

- Surcharge : ajouter un réplica (`lab.sh gpu-scale 2`), limiter le débit de la classe (rpm/tpm LiteLLM), activer KEDA.
- Classe RAG : prefill de prompts longs, modèle plus petit ou prompts plus courts.
- Ne pas relever le seuil du SLO pour faire taire l'alerte : décider d'abord si l'objectif est le bon.
