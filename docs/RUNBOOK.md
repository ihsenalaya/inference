# Runbook d'exploitation

**En une phrase.** Le mode d'emploi du quotidien : allumer, mettre en pause, détruire, changer de modèle, diagnostiquer, mesurer.

<!-- mots: scénario, cold start, gitops, taint -->
> **Mots à connaître**
> - **Scénario** : Un fichier `gitops/scenarios/*.yaml` qui choisit le modèle et les réglages ; un seul est actif.
> - **Cold start** : Délai entre « on demande un GPU / un pod » et « il répond ». Ici : **721 s** pour un nœud GPU, **~3,5 min** pour changer de modèle (observé).
> - **GitOps** : L'état voulu du cluster est écrit dans Git ; Argo CD le fait appliquer. On ne modifie pas le cluster à la main.
> - **Taint / toleration** : « Chasse-pods » posé sur le nœud GPU (`sku=gpu`) / autorisation pour les pods qui doivent y aller.
> - Tous les mots : [glossaire](sre/GLOSSAIRE.md).
<!-- /mots -->

## Cycle de vie (coût)

| Action | Commande | Effet sur la facture |
|---|---|---|
| Créer | `./lab.sh up` | ~0,71 $/h avec 1 T4 |
| Pause | `./lab.sh stop` | VM désallouées : plus de calcul facturé (disques et IP restent, quelques centimes) |
| Reprise | `./lab.sh start` | revérifie la convergence puis `smoke` |
| 2e GPU | `./lab.sh gpu-scale 2` | +0,526 $/h |
| Fin | `./lab.sh down --yes` | plus rien de facturé |

`down` demande une confirmation interactive : utiliser `--yes` dans un script. `start` peut échouer en `AllocationFailed` (capacité T4 malgré le quota, constatée en 2026) : le script le signale ;
réessayer plus tard, ou `down` puis `up`.

## Accès

`./lab.sh ui` ouvre les port-forwards (Grafana :3000, Prometheus :9090, Alertmanager :9093, Argo CD :8080, LiteLLM :4000) et affiche les identifiants.
Aucune IP publique n'est exposée ; pour exposer LiteLLM, restreindre à `MY_IP_CIDR`.

## Changer de scénario

`./lab.sh scenario small-fp16` modifie `gitops/active-azure.yaml`, commit, push ; Argo CD synchronise (le serving et LiteLLM changent ensemble).
Les réglages (max-model-len, gpu-memory-utilization, max-num-seqs, cache de préfixes, image vLLM...) sont dans `gitops/scenarios/<nom>.yaml`
(clé `vllm:` globale ou par modèle) ; `gitops/serving/chart/values.yaml` porte les valeurs par défaut.

## Diagnostic rapide

| Symptôme | Où regarder |
|---|---|
| Pod vLLM Pending | `kubectl describe pod` : `nvidia.com/gpu` annoncé ? `kubectl get nodes -o custom-columns=...` ; GPU Operator (`-n gpu-operator`) |
| `FailedCreatePodSandBox ... nvidia` | mélange des modes GPU : le pool doit être `gpu_driver=None` et AKS GPU managé désactivé (piège A1) |
| Démarrage très long | normal au premier lancement : driver, image vLLM (~9 Go), modèle ; durées dans BASELINE.md |
| HTTP 500 Gateway | `istio-proxy` : `ext_proc_error_gRPC_error_14` -> DestinationRule TLS vers l'EPP |
| Dashboard vide | Prometheus > Targets ; ports des ServiceMonitors ; `honorLabels` DCGM |
| Application Argo CD OutOfSync | `kubectl -n argocd get app <nom> -o yaml` ; les CRD arrivent avant les ressources (réessais) |

Chaque alerte a son runbook : `docs/runbooks/<Alerte>.md`.

## Mesurer

| Besoin | Commande |
|---|---|
| Un run simple | `RATE=2 DURATION=300 WARMUP=60 ./lab.sh bench steady` |
| Les 4 classes de charge | `INT_RATE=1 RAG_RATE=0.1 MT_RATE=0.5 BATCH_RATE=2.5 tests/classes.sh` (clé et goodput par classe) |
| Bruit de mesure (3 répétitions) | `PER_REQUEST=true tests/repeat_steady.sh <débit> 3 noise` puis `tests/noise.py 'results/*noise-r*'` |
| Signaux serveur et GPU d'un run | `ALIAS=lab-<classe> tests/run_window.py results/<run>` (Prometheus sur `127.0.0.1:19090`) |
| Essai d'alerte de burn rate | `tests/slo_alert_test.sh 0.5 600` (surcharge volontaire de la classe RAG) |
| Démarrage à froid | `python3 tests/coldstart.py` |

Règle : même profil, même durée, même échauffement, 3 répétitions avant de comparer ([module 1](formation/01-mesurer-sans-se-tromper.md)).

## Pièges d'environnement connus

- Si Docker Desktop est arrêté sous WSL, le lien `/usr/local/bin/kubectl` (qui pointe vers Docker Desktop) répond « Input/output error » et `lab.sh` s'arrête sans message pendant l'attente : installer un `kubectl` dans `~/.local/bin` (que `lab.sh` utilise en premier).
- Ne pas modifier `lab.sh` pendant qu'une commande tourne (bash lit le script au fur et à mesure).
- `pkill -f` peut tuer votre propre shell : arrêter les processus par numéro.

## Tests

- `tests/static.sh` : helm template + kubeconform de chaque composant, promtool, terraform, shellcheck, gitleaks (gratuit).
- `./lab.sh smoke` : chaîne complète sans charge ; `tests/burst_keda.sh` : KEDA.
- kind (sans GPU, faux vLLM) : `KIND_DISABLE=... ./lab.sh kind-up` ; la machine de dev (7,5 Go) ne tient pas toute la pile : désactiver des composants.
