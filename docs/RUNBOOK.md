# Runbook d'exploitation

## Cycle de vie (coût)

| Action | Commande | Effet sur la facture |
|---|---|---|
| Créer | `./lab.sh up` | ~0,71 $/h avec 1 T4 |
| Pause | `./lab.sh stop` | VM désallouées : plus de calcul facturé (disques et IP restent, quelques centimes) |
| Reprise | `./lab.sh start` | revérifie la convergence puis `smoke` |
| 2e GPU | `./lab.sh gpu-scale 2` | +0,526 $/h |
| Fin | `./lab.sh down --yes` | plus rien de facturé |

`start` peut échouer en `AllocationFailed` (capacité T4 malgré le quota, constatée en 2026) : le script le signale ;
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

## Tests

- `tests/static.sh` : helm template + kubeconform de chaque composant, promtool, terraform, shellcheck, gitleaks (gratuit).
- `./lab.sh smoke` : chaîne complète sans charge ; `tests/burst_keda.sh` : KEDA.
- kind (sans GPU, faux vLLM) : `KIND_DISABLE=... ./lab.sh kind-up` ; la machine de dev (7,5 Go) ne tient pas toute la pile : désactiver des composants.
