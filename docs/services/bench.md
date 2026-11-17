# inference-perf (banc de charge)

**En une phrase.** inference-perf est le testeur de charge : il envoie des requêtes à un rythme choisi et mesure ce que le cluster en fait (délais, débit, erreurs).

<!-- mots: bench, boucle ouverte, échauffement, percentile, goodput, clé virtuelle -->
> **Mots à connaître**
> - **Bench (inference-perf)** : Génère de la charge pour mesurer.
> - **Boucle ouverte / fermée** : Ouverte : on impose un débit d'arrivée (comme de vrais utilisateurs) ; elle révèle les files. Fermée : N clients attendent chacun leur réponse ; elle masque la surcharge.
> - **Échauffement** : Début de run exclu de la mesure (caches vides, régime pas encore stable). Ici 60 s.
> - **Percentile (p50, p95, p99)** : p95 = 95 % des requêtes vont plus vite que cette valeur. Le p50 est la médiane. Le p95 montre les cas lents.
> - **Goodput** : Débit des requêtes **réussies et assez rapides** (qui respectent le SLO), pas le débit brut.
> - **Clé virtuelle** : Clé d'API LiteLLM par client ; l'alias de la clé sert ici à identifier la **classe de charge**.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Rôle
Génère une **charge d'inférence contrôlée** et mesure TTFT, TPOT, latences, débits, erreurs. Outil de `kubernetes-sigs`, version **v0.7.0** (image `quay.io/inference-perf/inference-perf@sha256:d247e6ad…`).

## Place dans l'architecture
Hors du chemin de production : lancé **à la demande** par `lab.sh bench <profil>` comme **Job Kubernetes** dans `inference`, sur le pool **système** (`nodeSelector workload=platform`), jamais sur le GPU.

## Relations
Cible : LiteLLM (`--target litellm`, défaut, chemin complet) ou la Gateway Istio directe (`--target gateway`) pour isoler le surcoût de LiteLLM. Lit Prometheus pour les métriques serveur (option).

## Configuration retenue (config : `gitops/bench`)
Profils (`profiles/*.yaml`) : `smoke`, `sweep`, `steady`, `shared-prefix`, `multi-turn`, `long-prompt`, `burst`, et pour les classes de charge SLO `interactive` et `batch` (+ `long-prompt` = RAG, `multi-turn` = multi-tour). Particularités imposées par v0.7.0 (observé) :
- le générateur **synthétique** n'accepte que l'API `completion` ; `shared_prefix` accepte aussi `chat` ;
- le **sweep automatique échoue** (`index 1 is out of bounds`) : paliers explicites ;
- pas de bloc `observability` dans la config ;
- charge en **boucle ouverte** (`type: constant`, débit imposé) : la file d'attente n'est pas masquée.
Les profils `steady`, `interactive`, `batch`, `long-prompt` et `multi-turn` acceptent un **échauffement** (`warmup`, stage 0) exclu de la mesure. Options de `lab.sh bench` (variables d'environnement) : `RATE`, `DURATION`, `WARMUP`, `RAG_RATE` (débit du profil RAG), `PER_REQUEST=true` (un CSV compact par requête : `requests.csv`, sert à calculer le goodput), `BENCH_KEY=lab-<classe>` (clé virtuelle de la classe), `RESULT_TAG`, `BENCH_TIMEOUT`. `tests/classes.sh` enchaîne les 4 classes.
Ressources du job : requests 500 m / 1 Gi, limite mémoire 3 Gi. Le tokenizer est téléchargé depuis Hugging Face à chaque run.

## Authentification
Clé virtuelle `lab-bench` par défaut, ou la clé d'une classe avec `BENCH_KEY` (lue dans le secret `litellm-keys`, passée en `api_key`). `lab.sh` **masque la clé** dans les résultats avant de les enregistrer (un incident antérieur l'avait laissée dans Git).

## Données traitées
Des prompts **synthétiques** (jeux générés ; aucune donnée réelle). Résultats : JSON par palier et, en mode par requête, `requests.csv` dans `results/<date>-<scénario>-<profil>[-tag]/` ; `tests/goodput.py` calcule le goodput, `tests/run_window.py` ajoute les signaux serveur et GPU de la même fenêtre.

## Contribution à l'inférence
C'est l'instrument de mesure : toutes les valeurs de `docs/BASELINE.md` viennent de lui. Bruit de mesure (3 répétitions, échauffement exclu : 7B AWQ à 1 req/s, 1,5B FP16 à 2 req/s) : voir [module 1](../formation/01-mesurer-sans-se-tromper.md).

## Pannes et diagnostic (observé)
| Symptôme | Cause |
|---|---|
| `Unsupported API type Chat` | profil synthétique en API `chat` |
| `Extra inputs are not permitted ... observability` | clé inexistante en v0.7.0 |
| job qui ne finit pas / résultats vides | `lab.sh bench` attend la fin **ou l'échec** du job (jusqu'à `BENCH_TIMEOUT`) ; les résultats sont affichés en fin de log entre `===LAB-RESULTS-BEGIN===` et `END` |
| `Extra inputs are not permitted ... max_model_len` (profil multi-tour) | clé inexistante dans `shared_prefix` en v0.7.0 (retirée le 17/11) |
| multi-tour : beaucoup d'erreurs 400 `ContextWindowExceededError` | à 2 req/s les conversations simulées dépassent `max-model-len` (4 096) : utiliser 0,5 req/s |
| extraction des résultats interminable (WSL) | ancien comportement (une écriture par ligne) ; corrigé : une écriture par fichier |
| premier palier d'un sweep en échec | LiteLLM redémarre après un changement de scénario |
| pod de bench `Pending` sur kind | nœud sans label `workload=platform` |
