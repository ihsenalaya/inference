# inference-perf (banc de charge)

## Rôle
Génère une **charge d'inférence contrôlée** et mesure TTFT, TPOT, latences, débits, erreurs. Outil de `kubernetes-sigs`, version **v0.7.0** (image `quay.io/inference-perf/inference-perf@sha256:d247e6ad…`).

## Place dans l'architecture
Hors du chemin de production : lancé **à la demande** par `lab.sh bench <profil>` comme **Job Kubernetes** dans `inference`, sur le pool **système** (`nodeSelector workload=platform`), jamais sur le GPU.

## Relations
Cible : LiteLLM (`--target litellm`, défaut, chemin complet) ou la Gateway Istio directe (`--target gateway`) pour isoler le surcoût de LiteLLM. Lit Prometheus pour les métriques serveur (option).

## Configuration retenue (config : `gitops/bench`)
Profils (`profiles/*.yaml`) : `smoke`, `sweep`, `steady`, `shared-prefix`, `multi-turn`, `long-prompt`, `burst`. Particularités imposées par v0.7.0 (observé) :
- le générateur **synthétique** n'accepte que l'API `completion` ; `shared_prefix` accepte aussi `chat` ;
- le **sweep automatique échoue** (`index 1 is out of bounds`) : paliers explicites ;
- pas de bloc `observability` dans la config ;
- charge en **boucle ouverte** (`type: constant`, débit imposé) : la file d'attente n'est pas masquée.
Le profil `steady` accepte un **échauffement** (`warmup`, stage 0) exclu de la mesure (stage 1).
Ressources du job : requests 500 m / 1 Gi, limite mémoire 3 Gi. Le tokenizer est téléchargé depuis Hugging Face à chaque run.

## Authentification
Clé virtuelle `lab-bench` (lue dans le secret `litellm-keys`, passée en `api_key`). `lab.sh` **masque la clé** dans les résultats avant de les enregistrer (un incident antérieur l'avait laissée dans Git).

## Données traitées
Des prompts **synthétiques** (jeux générés ; aucune donnée réelle). Résultats : JSON par palier dans `results/<date>-<scénario>-<profil>/`.

## Contribution à l'inférence
C'est l'instrument de mesure : toutes les valeurs de `docs/BASELINE.md` viennent de lui. Bruit de mesure (7B AWQ, 3 répétitions à 1 req/s, échauffement exclu) : voir `docs/sre/ETAT-DES-LIEUX.md`.

## Pannes et diagnostic (observé)
| Symptôme | Cause |
|---|---|
| `Unsupported API type Chat` | profil synthétique en API `chat` |
| `Extra inputs are not permitted ... observability` | clé inexistante en v0.7.0 |
| job qui ne finit pas / résultats vides | `lab.sh bench` attend `BENCH_TIMEOUT` ; les résultats sont affichés en fin de log entre `===LAB-RESULTS-BEGIN===` et `END` |
| premier palier d'un sweep en échec | LiteLLM redémarre après un changement de scénario |
| pod de bench `Pending` sur kind | nœud sans label `workload=platform` |
