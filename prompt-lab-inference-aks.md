# Prompt — Lab d'inférence LLM sur AKS (2 × T4)

vLLM · llm-d · KServe · Istio · LiteLLM · KEDA · Prometheus / Grafana / Alertmanager · Loki — GitOps, un seul script.

Version du 16/11/2026.

**Mode d'emploi.** (1) Ouvre un dossier vide sur un poste où `az` (connecté), `kubectl`, `helm`, `terraform`, `git` et `gh` sont installés. (2) Colle tout le texte ci-dessous dans ton agent de code. (3) Réponds à ses questions de la phase 0. (4) Valide le point d'arrêt avant la création des ressources payantes.

---

## 1. Rôle et mission

Tu es un ingénieur plateforme IA senior (AKS, Kubernetes, GPU NVIDIA, serving de LLM, observabilité, GitOps).

Ta mission : construire, déployer et valider un lab d'inférence complet sur AKS, entièrement automatisé (un script + GitOps) et instrumenté de bout en bout. Ce lab sert à apprendre à optimiser les GPU, les modèles et le cluster d'inférence. Ce n'est pas une production : il doit être reproductible, lisible, bon marché et, surtout, mesurable.

Trois résultats attendus :

1. un dépôt Git complet (infrastructure, GitOps, script, tests, documentation) ;
2. le cluster déployé et vert ;
3. un rapport de référence `docs/BASELINE.md` avec les premières mesures et les anomalies constatées. Je m'en servirai ensuite pour travailler l'optimisation : ne l'applique pas toi-même.

## 2. Contexte et contraintes

- Abonnement Azure personnel. Quota GPU : 2 VM `Standard_NC4as_T4_v3` (4 vCPU, 28 Gio de RAM, 1 GPU T4 de 16 Go, disque temporaire de 180 Go). Aucune VM T4 n'existe actuellement : le quota est libre.
- AKS en tier Free. Le coût doit être maîtrisé : tout doit pouvoir être arrêté, redémarré et détruit par le script.
- Tout est open source et tourne dans le cluster : pas d'Azure Monitor managé, pas de Managed Prometheus ni de Managed Grafana, pas d'add-on Istio d'AKS, pas de KAITO (il ne supporte pas le T4).
- Je maîtrise Azure, Terraform et Kubernetes. Je débute en optimisation d'inférence : documente le pourquoi des choix d'inférence, pas les bases de Kubernetes.
- Documentation et commentaires en français, noms techniques en anglais.

## 3. Paramètres

Demande-les-moi au début s'ils ne sont pas dans `.env` :

| Variable | Rôle |
|---|---|
| `AZ_SUBSCRIPTION_ID` | abonnement cible |
| `AZ_LOCATION` | région où mon quota T4 existe |
| `PREFIX` | préfixe des ressources (défaut `inflab`) |
| `GIT_REPO_URL` | dépôt GitHub privé du lab (crée-le avec `gh` s'il n'existe pas) |
| `HF_TOKEN` | optionnel, jeton Hugging Face |
| `ALERT_WEBHOOK_URL` | optionnel, récepteur des alertes (Teams, Slack, ntfy) |
| `MY_IP_CIDR` | optionnel, pour restreindre l'API server et toute exposition |

Récupère le prix horaire de la VM GPU et de la VM système pour la région choisie (API Azure Retail Prices). Si tu n'y arrives pas, demande-les-moi. Ils servent au calcul de coût.

## 4. Règles de travail

1. **Vérifie avant d'écrire.** Les versions et faits de ce prompt datent du 16/11/2026. Avant de pinner quoi que ce soit, contrôle la documentation officielle et les notes de version du composant. En cas d'écart avec ce prompt, la source officielle gagne : note l'écart dans `docs/DECISIONS.md`.
2. **Pinne tout.** Charts, images (par digest pour LiteLLM et vLLM), providers Terraform. Jamais de `latest`. Centralise dans `versions.yaml` (version, date, lien source).
3. **KServe mène les versions de ses dépendances.** Prends les versions de Gateway API, de l'Inference Extension (GIE), de LeaderWorkerSet et de cert-manager dans le script `llmisvc-dependency-install.sh` de la release KServe retenue, pas dans la dernière version de chaque projet.
4. **Ne suppose aucun nom de métrique.** Les noms changent d'une version à l'autre. Lis les `/metrics` réels avant d'écrire une requête PromQL, une règle ou un panneau.
5. **Avance par phases** (section 17). Ne passe pas à la suivante tant que les vérifications de la phase en cours sont rouges.
6. **Dépenses.** Tout ce qui est gratuit se fait sans me demander. Demande-moi une seule confirmation avant le premier `terraform apply`, avec une estimation du coût horaire.
7. **Périmètre.** Ne touche qu'au resource group du lab.
8. **Secrets.** Jamais dans Git. Le script les crée dans le cluster à partir de `.env` (ignoré par Git) et génère ceux qui manquent.
9. **Journal.** Tiens `docs/DECISIONS.md` : décision, raison, source, date.
10. **Pas de contournement silencieux.** Si un composant imposé ne peut pas fonctionner comme décrit, arrête-toi, explique et propose. Ne remplace aucun composant sans mon accord. Seule exception : le modèle de secours (section 8).

## 5. Architecture cible

Chaîne d'une requête :

```
client ou banc de charge
  -> LiteLLM         AI gateway : clés virtuelles, budgets, quotas, routage par modèle
  -> Gateway Istio   Gateway API, classe "istio"
  -> HTTPRoute -> InferencePool + EPP llm-d
                     choix du pod : cache de préfixes, file d'attente, charge
  -> pods vLLM       1 GPU T4 par pod
```

La partie Gateway → vLLM est déclarée par un `LLMInferenceService` KServe. L'autoscaling passe par KEDA (`spec.scaling.keda`). L'infrastructure est en Terraform, tout le reste en GitOps avec Argo CD.

| Composant | Rôle | Référence au 16/11/2026 |
|---|---|---|
| AKS (Free) | cluster | version GA la plus récente supportée par le GPU Operator et KServe (des retours récents tournent en 1.34) |
| NVIDIA GPU Operator | driver, toolkit, device plugin, DCGM exporter, NFD | v26.7.x |
| KServe `LLMInferenceService` | plan de contrôle du serving | v0.21.0 (25/09/2026), charts OCI `kserve-llmisvc-crd`, `kserve-llmisvc-resources`, `kserve-runtime-configs` |
| llm-d | scheduler / EPP (routage intelligent) | livré par KServe, à la version que KServe pinne. Le projet est en v1.0 (20/10/2026) : son dépôt est la source des dashboards et des règles d'alerte |
| vLLM | moteur d'inférence | dernière version : v0.33.0 (02/11/2026). Version à retenir selon le piège B2 |
| Istio (upstream, Helm) | implémentation Gateway API + Inference Extension | dernière stable (≥ 1.29, où le support GIE est passé en bêta), compatible avec la version de GIE pinnée par KServe |
| Gateway API, GIE, LeaderWorkerSet, cert-manager | dépendances de KServe | versions pinnées par KServe v0.21.0 |
| LiteLLM + PostgreSQL | AI gateway | dernière stable (≥ v1.106), image pinnée par digest ; PostgreSQL 16+ |
| KEDA | autoscaling | ≥ 2.21 |
| kube-prometheus-stack | Prometheus, Alertmanager, Grafana | dernière stable |
| Loki + Alloy | logs | Loki 3.7.x, chart `grafana-community/loki` en mode `Monolithic` ; Alloy, chart `grafana/alloy` |
| Argo CD | GitOps | dernière stable |
| inference-perf, GuideLLM | génération de charge | dernières stables |

Ce qui est volontairement exclu : désagrégation prefill/decode, serving multi-nœud (LeaderWorkerSet reste une simple dépendance), Envoy Gateway, Envoy AI Gateway, WVA (Workload Variant Autoscaler).

## 6. Pièges connus (retours d'expérience)

Chaque point ci-dessous a déjà fait perdre du temps à quelqu'un. Traite-les explicitement et consigne ce que tu constates.

### A. AKS et GPU

- **A1. Deux modes GPU exclusifs.** Le GPU Operator gère tout : crée le pool GPU sans driver AKS (`gpu_driver = "None"` côté azurerm, équivalent de `--gpu-driver none`, Azure CLI ≥ 2.72.2) et sans GPU managé AKS (`--enable-managed-gpu` reste à `false` : ce mode installe son propre device plugin et son propre DCGM exporter, qui entrent en conflit avec ceux de l'opérateur). Côté opérateur : `driver.enabled=true` et `toolkit.enabled=true`. Mélanger les deux modes donne `FailedCreatePodSandBox: no runtime for "nvidia" is configured` et zéro `nvidia.com/gpu` annoncé. Le réglage ne s'applique qu'à la création du pool.
- **A2. Un seul OS.** Le GPU Operator ne supporte pas plusieurs versions d'OS dans un même cluster AKS : même OS SKU (Ubuntu) pour les deux pools.
- **A3. Driver et CUDA.** Le driver installé par l'opérateur doit supporter le T4 et couvrir la version de CUDA embarquée dans l'image vLLM retenue (les notes de la 0.33.0 annoncent PyTorch 2.14 ; l'abandon de CUDA 12.9 est à confirmer). Vérifie la matrice avant de pinner `driver.version`.
- **A4. Capacité.** Des `AllocationFailed` sur `NC4as_T4_v3` ont été rapportés en 2026 malgré un quota disponible, notamment au redémarrage après désallocation. `preflight` vérifie le quota (famille « Standard NCASv3_T4 », 8 vCPU) et la disponibilité du SKU ; `up` et `start` traitent cette erreur avec un message clair ; la région reste une variable.
- **A5. Taint.** Pool GPU avec `sku=gpu:NoSchedule`. Tolérations à poser sur tout ce qui doit tourner sur ces nœuds : opérandes du GPU Operator, worker NFD, Alloy, node-exporter, pods vLLM.
- **A6. Démarrage lent.** Un nœud GPU neuf enchaîne installation du driver, pull d'une image vLLM de plusieurs Go, téléchargement puis chargement du modèle. Prévois des timeouts larges dans le script et des `startupProbe` généreuses. Mesure chaque durée : c'est un sujet d'optimisation.

### B. T4 (Turing, compute capability 7.5) et vLLM

- **B1. dtype.** 7.5 est le minimum supporté par vLLM. Le T4 n'a pas de bfloat16 natif : force `--dtype float16`.
- **B2. Backend d'attention.** Sur T4, les versions récentes de vLLM ne sélectionnent que `TRITON_ATTN` ou `FLEX_ATTENTION` : FlashAttention exige SM80+ et FlashInfer est bridé à SM80+ depuis la v0.24.0. Depuis Triton 3.3, ces noyaux n'utilisent plus les tensor cores sur Turing. Mesure publiée sur T4 avec un petit modèle : prefill de 8 000 tokens en ~9,5 s contre ~0,6 s avec FlashInfer. Suivi : issue vLLM #60821, PR #55380 (retour de FlashInfer sur SM75), PR #61015 (avertissement). À faire :
  1. relever dans les logs la ligne indiquant le backend d'attention retenu ;
  2. vérifier si la PR #55380 est intégrée à une release ; si oui, préférer cette release ;
  3. sinon, partir de l'image vLLM prévue par KServe v0.21.0, limiter `--max-model-len` à 4096 pour la base, et décrire dans `BASELINE.md` une expérience A/B de version d'image ;
  4. ne pas utiliser de fork communautaire sans mon accord.
- **B3. Quantization.** Sur Turing : AWQ, GPTQ, Marlin (hors MXFP4) et INT8 W8A8 (llm-compressor) sont supportés. FP8 W8A8 ne l'est pas. Le cache KV en FP8 n'est pas disponible avec le backend Triton.
- **B4. Gemma 3.** Instable en float16 sur T4 : ne pas l'utiliser.
- **B5. Test de bon sens par modèle.** Une requête `/v1/chat/completions` à `temperature=0` et une à `temperature=0.7` doivent toutes deux rendre un texte cohérent : pas de crash CUDA, pas de sortie dégénérée ou répétitive. Si vLLM expose `vllm:corrupted_requests` (NaN dans les logits ; la détection peut demander une activation, vérifie la doc), elle doit rester à 0.

### C. KServe, llm-d, Istio

- **C1. Ordre d'installation.** CRDs Gateway API et GIE avant istiod. Sinon istiod ne les voit pas et doit être redémarré.
- **C2. Istio et GIE.** Installe Istio upstream par Helm (profil minimal) avec les variables d'environnement de pilot `SUPPORT_GATEWAY_API_INFERENCE_EXTENSION=true` et `ENABLE_GATEWAY_API_INFERENCE_EXTENSION=true`. `GatewayClass` : `istio`. Vérifie que la version d'Istio est conforme à la version de GIE (InferencePool v1) imposée par KServe. N'active pas l'add-on Istio d'AKS : il est incompatible avec un Istio auto-géré.
- **C3. KServe sans Envoy.** KServe utilise Envoy Gateway par défaut (valeur `kserve.controller.gateway.ingressGateway.gatewayClassName`, défaut `envoy`) et cite Envoy AI Gateway dans ses prérequis. Ici : classe `istio`, ni Envoy Gateway ni Envoy AI Gateway. Crée une `Gateway` dédiée de classe `istio` et référence-la dans `spec.router.gateway.refs`. Examine les valeurs `kserve.controller.gateway.ingressGateway.{enableGatewayApi, createGateway, kserveGateway, gatewayClassName}` du chart `kserve-llmisvc-resources`. Contrôle dans les logs du contrôleur llmisvc qu'il ne réclame pas de CRDs Envoy AI Gateway absentes. Si c'est le cas, arrête-toi et expose les options.
- **C4. Istio en passerelle seulement.** Pas d'injection de sidecar dans les namespaces d'inférence (issue KServe #5331 : conflit de classification de protocole sur le port ext_proc 9002 de l'EPP). Si l'appel ext_proc Gateway → EPP échoue sur le TLS, consulte le guide Istio de GIE (DestinationRule vers le service de l'EPP). C'est un point à vérifier, pas une certitude.
- **C5. API.** Les exemples récents utilisent `serving.kserve.io/v1alpha2` ; `v1alpha1` reste servie. Tranche avec `kubectl explain`. `spec.replicas` et `spec.scaling` sont mutuellement exclusifs.
- **C6. URL.** KServe expose le service sous un préfixe de chemin `/<namespace>/<nom>/v1/...`. Lis l'URL dans `.status.url`.
- **C7. Nom de port.** En v0.21.0, le port du Service workload s'appelle `http` (c'était `https` en 0.18). Un ServiceMonitor qui cible l'ancien nom ne collecte plus rien : dashboards vides et KEDA inerte.
- **C8. Gateway non programmée.** `Programmed: False` : lire les logs d'istiod. Si la Gateway est un jour exposée par un Azure Load Balancer, ajouter l'annotation `service.beta.kubernetes.io/port_80_health-probe_protocol: tcp`.
- **C9. Composants annexes.** D'après ses notes de version, KServe v0.21.0 peut déployer des composants supplémentaires pour le scheduler (tokenisation). Place-les sur le pool système et compte leurs ressources.

### D. Observabilité

- **D1. kube-prometheus-stack sur AKS.** Désactive le scraping de kube-scheduler, kube-controller-manager et etcd (plan de contrôle managé, donc fausses alertes). Mets `serviceMonitorSelectorNilUsesHelmValues`, `podMonitorSelectorNilUsesHelmValues` et `ruleSelectorNilUsesHelmValues` à `false` pour découvrir les objets de tous les namespaces. Avec Argo CD : `ServerSideApply=true` pour les CRDs.
- **D2. DCGM.** `dcgmExporter.serviceMonitor.enabled=true`, intervalle 15 s, `honorLabels: true`. Sans `honorLabels`, les labels `pod` et `namespace` du workload qui consomme le GPU sont renommés `exported_*` et la jointure avec les métriques vLLM casse. Liste de métriques personnalisée par `dcgmExporter.config.name`.
- **D3. EPP.** `/metrics` sur le port 9090, parfois protégé par jeton (ServiceAccount + RBAC). Les noms diffèrent selon la version : `llm_d_epp_*` dans la doc llm-d récente, `inference_*` dans des versions plus anciennes.
- **D4. vLLM.** Noms actuels : `vllm:num_requests_running`, `vllm:num_requests_waiting`, `vllm:kv_cache_usage_perc`, `vllm:time_to_first_token_seconds`, `vllm:inter_token_latency_seconds`, `vllm:e2e_request_latency_seconds`, `vllm:request_queue_time_seconds`, `vllm:request_prefill_time_seconds`, `vllm:request_decode_time_seconds`, `vllm:prompt_tokens`, `vllm:generation_tokens`, `vllm:prefix_cache_queries`, `vllm:prefix_cache_hits`, `vllm:num_preemptions`, `vllm:request_success` (suffixe `_total` côté Prometheus pour les compteurs). Beaucoup de dashboards publics utilisent d'anciens noms (par exemple `vllm:gpu_cache_usage_perc`) : corrige-les.
- **D5. Loki.** Le chart open source vit dans `grafana-community/helm-charts` depuis le 16/03/2026. `deploymentMode: Monolithic`. Promtail est en fin de vie depuis le 02/03/2026 : collecte avec Alloy. Le MinIO embarqué du chart est retiré : stockage filesystem sur PVC.

### E. LiteLLM

- **E1. Chaîne d'approvisionnement.** Les versions PyPI 1.82.7 et 1.82.8 ont été compromises le 24/03/2026. Image officielle pinnée par digest, version issue du pipeline refait (v1.83.0 ou plus), jamais `latest`.
- **E2. Backend vLLM.** Préfixe de fournisseur `hosted_vllm/`, `api_base` terminé par `/v1`.
- **E3. Base de données.** PostgreSQL obligatoire pour les clés virtuelles, les équipes et les dépenses. `LITELLM_MASTER_KEY` et `LITELLM_SALT_KEY` : la salt key ne doit plus jamais changer.
- **E4. Prometheus.** Disponible en open source : `callbacks: ["prometheus"]`. Utilise le port de métriques dédié (`--prometheus_metrics_port`, v1.101.0 ou plus) et `PROMETHEUS_MULTIPROC_DIR` s'il y a plusieurs workers. Ce port ne sort pas du cluster.
- **E5. Sondes.** `/health/liveliness` et `/health/readiness`.

### F. KEDA

- **F1. Signal.** `vllm:num_requests_waiting` par réplica. Ni CPU ni utilisation GPU.
- **F2. Délais réels.** Retour d'expérience sur KServe 0.21 : la décision de scale-out tombe en une vingtaine de secondes, mais un nouveau réplica met plusieurs minutes à charger le modèle (environ 3,5 min mesurées). Donc pas de scale-to-zero par défaut, et un scale-down stabilisé sur 5 min.

## 7. Infrastructure (Terraform, provider azurerm)

- Resource group `${PREFIX}-rg`. AKS tier Free, identité managée, OIDC issuer et workload identity activés, Azure CNI Overlay, aucun add-on de monitoring Azure.
- Auto-upgrade du cluster et de l'OS des nœuds désactivés : une nouvelle image de nœud change le noyau et relance l'installation du driver, ce qui fausse la reproductibilité.
- **Pool système** : 1 nœud d'au moins 8 vCPU et 32 Gio (par exemple `Standard_D8s_v5`). Il héberge toute la plateforme. Dimensionne les requests et limits pour que tout tienne ; sinon, propose-moi un ajustement avant de déployer.
- **Pool GPU** : `Standard_NC4as_T4_v3`, `gpu_driver = "None"`, taint `sku=gpu:NoSchedule`, label `workload=inference`, disque OS éphémère si le SKU le permet, nombre de nœuds piloté par variable (0 à 2, défaut 2), autoscaler de nœuds désactivé par défaut.
- State Terraform local par défaut, backend azurerm optionnel.
- Aucune ressource payante annexe (pas d'ACR, pas de Key Vault, pas de Log Analytics). Aucune IP publique par défaut : services en ClusterIP, accès par port-forward via le script. Exposition optionnelle de LiteLLM par LoadBalancer restreint à `MY_IP_CIDR`.

## 8. Modèles et scénarios

| Alias | Dépôt Hugging Face | Précision | Usage |
|---|---|---|---|
| `qwen-7b-awq` | `Qwen/Qwen2.5-7B-Instruct-AWQ` | AWQ 4 bits | modèle principal, réaliste |
| `qwen-1.5b` | `Qwen/Qwen2.5-1.5B-Instruct` | FP16 | itérations rapides, routage, montée en charge |
| `qwen-1.5b-awq` | `Qwen/Qwen2.5-1.5B-Instruct-AWQ` | AWQ 4 bits | comparaison FP16 / quantizé à taille égale |
| `bge-m3` | `BAAI/bge-m3` | FP16 | embeddings : second type de charge, partage de GPU |

Arguments vLLM de base : `--dtype float16`, `--max-model-len 4096`, `--gpu-memory-utilization 0.90`. Surcharge le conteneur `main` du `LLMInferenceService` sans casser les arguments injectés par les presets (`baseRefs`). Requests CPU et mémoire des pods vLLM calées sur l'allocatable réel d'un nœud T4.

Tous les réglages d'optimisation sont externalisés dans un fichier de valeurs par scénario : `max-model-len`, `gpu-memory-utilization`, `max-num-seqs`, `max-num-batched-tokens`, cache de préfixes, niveau d'optimisation (`-O`), image vLLM, poids des scorers de l'EPP (`prefix-cache-scorer`, `load-aware-scorer`), réplicas ou scaling.

Scénarios, en overlays Kustomize, un seul actif à la fois. La bascule se fait par `lab.sh scenario <nom>` : commit Git puis synchronisation Argo CD.

| Scénario | Priorité | Contenu |
|---|---|---|
| `baseline-7b` (défaut) | P0 | `qwen-7b-awq`, 2 réplicas fixes (1 par T4), routage llm-d |
| `baseline-7b-keda` | P0 | le même, avec `spec.scaling.keda`, 1 à 2 réplicas |
| `small-fp16` | P0 | `qwen-1.5b`, 2 réplicas fixes |
| `quant-ab` | P1 | GPU 1 : `qwen-1.5b` ; GPU 2 : `qwen-1.5b-awq` (deux `LLMInferenceService`) |
| `multi-model` | P1 | GPU 1 : `qwen-7b-awq` ; GPU 2 : `qwen-1.5b` ; LiteLLM route par modèle, avec fallback |
| `gpu-sharing` | P1 | time-slicing du GPU Operator (2 parts par T4) : `qwen-1.5b` et `bge-m3` sur le même T4 ; variante MPS documentée. Le T4 ne supporte pas MIG |

P0 : déployé et validé de bout en bout. P1 : livré, rendu validé (`kustomize build` et dry-run côté serveur), test de bascule si le temps le permet.

Modèle de secours : si un modèle échoue au test B5 sur T4, remplace-le par un équivalent (même ordre de taille, licence permissive) et documente la raison.

Poids : `hf://` avec le storage initializer de KServe. `HF_TOKEN` passe par un Secret. Mesure le temps de cold start.

## 9. GitOps (Argo CD)

- Argo CD installé par Helm par le script, puis une application racine (app-of-apps) qui pointe sur le dépôt. Dépôt privé : deploy key créée par le script avec `gh`.
- Auto-sync, self-heal, prune, retries, `ServerSideApply`. Ordre garanti par des sync waves.
- Charts tiers référencés à une version exacte ; leurs valeurs vivent dans le dépôt.

Ordre des vagues :

| Vague | Contenu |
|---|---|
| 0 | namespaces ; CRDs : prometheus-operator, Gateway API, GIE, cert-manager |
| 1 | cert-manager, kube-prometheus-stack |
| 2 | Istio (`base`, `istiod`), GPU Operator, KEDA, LeaderWorkerSet, Loki, Alloy |
| 3 | KServe llmisvc (CRDs, contrôleur, runtime-configs), `Gateway` Istio |
| 4 | scénario de serving, PostgreSQL, LiteLLM |
| 5 | ServiceMonitors et PodMonitors, règles, dashboards, banc de charge |

Structure du dépôt :

```
.
├── lab.sh
├── .env.example
├── versions.yaml
├── infra/terraform/
├── gitops/
│   ├── bootstrap/        # Argo CD + application racine
│   ├── platform/         # cert-manager, CRDs, istio, gpu-operator, keda, lws, kserve
│   ├── observability/    # kube-prometheus-stack, loki, alloy, monitors, rules, dashboards
│   ├── gateway/          # Gateway Istio, litellm, postgres
│   ├── serving/          # base/ et scenarios/<nom>/
│   └── bench/            # profils inference-perf et guidellm
├── tests/                # smoke, promtool, kubeconform
├── results/
└── docs/
```

## 10. Passerelles

**Istio.** Charts `base` et `istiod`, profil minimal, variables GIE (piège C2), pas de sidecar. Une `Gateway` `inference-gateway` de classe `istio`, Service en ClusterIP. Métriques d'istiod et du proxy de la gateway collectées. Access logs Envoy en JSON sur stdout, pour Loki.

**LiteLLM.** Deployment + PostgreSQL (StatefulSet, PVC `managed-csi`). Configuration en ConfigMap générée par scénario : chaque entrée de `model_list` pointe sur `hosted_vllm/<modèle>` avec, en `api_base`, l'URL interne de la Gateway Istio, le préfixe du `LLMInferenceService` et `/v1`. Le script crée deux équipes et leurs clés virtuelles : `lab-bench` (sans limite) et `lab-user` (budget, rpm et tpm), pour produire des métriques par équipe et tester les quotas.

**Deux chemins de test**, à garder tous les deux : par LiteLLM (chaîne complète) et directement par la Gateway Istio. Leur écart mesure le surcoût de chaque étage.

## 11. Autoscaling (KEDA)

KEDA installé par Helm, avec son ServiceMonitor. Scénario `baseline-7b-keda`, structure indicative à valider avec `kubectl explain llminferenceservice.spec.scaling.keda` :

```yaml
spec:
  scaling:
    minReplicas: 1
    maxReplicas: 2
    keda:
      pollingInterval: 15
      cooldownPeriod: 300
      triggers:
        - type: prometheus
          metadata:
            serverAddress: http://<service-prometheus>.<namespace>.svc:9090
            query: sum(vllm:num_requests_waiting{<labels réels du modèle>})
            threshold: "2"
```

- Vérifie que KServe crée bien le `ScaledObject` et le HPA.
- Pas de scale-to-zero par défaut (piège F2).
- Test : le profil `burst` doit faire passer de 1 à 2 réplicas, puis revenir à 1. Mesure trois délais : décision, pod Ready, premier token servi par le nouveau réplica.
- Expose dans Grafana : réplicas désirés et prêts, valeur du trigger, événements de scaling.

## 12. Observabilité

C'est le cœur du lab. Tout est en code, dans Git.

### 12.1 Collecte

| Cible | Méthode | Attention |
|---|---|---|
| GPU (DCGM exporter) | ServiceMonitor du GPU Operator | piège D2 |
| vLLM `/metrics` | ServiceMonitor ou PodMonitor | piège C7 |
| EPP llm-d | ServiceMonitor | piège D3 |
| Gateway Istio (Envoy), istiod | PodMonitor | |
| LiteLLM | ServiceMonitor sur le port dédié | piège E4 |
| KEDA, Argo CD, KServe, cert-manager, Loki, Alloy | ServiceMonitors des charts | |
| kube-state-metrics, node-exporter, kubelet / cAdvisor | inclus dans la stack | |

Scrape à 15 s pour vLLM, DCGM et l'EPP. Rétention Prometheus de 7 jours sur PVC.

Liste DCGM minimale : `DCGM_FI_DEV_GPU_UTIL`, `DCGM_FI_DEV_MEM_COPY_UTIL`, `DCGM_FI_DEV_FB_USED`, `DCGM_FI_DEV_FB_FREE`, `DCGM_FI_DEV_POWER_USAGE`, `DCGM_FI_DEV_TOTAL_ENERGY_CONSUMPTION`, `DCGM_FI_DEV_GPU_TEMP`, `DCGM_FI_DEV_XID_ERRORS`, `DCGM_FI_DEV_PCIE_REPLAY_COUNTER`, compteurs ECC, raisons de throttling, et les métriques de profiling `DCGM_FI_PROF_GR_ENGINE_ACTIVE`, `DCGM_FI_PROF_DRAM_ACTIVE`, `DCGM_FI_PROF_PCIE_TX_BYTES`, `DCGM_FI_PROF_PCIE_RX_BYTES`. Retire celles que le T4 ou la version de l'exporter ne fournit pas.

### 12.2 Recording rules (préfixe `lab:`)

- **Latence** : TTFT p50, p95, p99 ; latence inter-token p50, p95 ; latence de bout en bout p95 ; temps de file p95 ; prefill p95 ; decode p95. Par modèle et par pod.
- **Débit** : tokens générés par seconde, tokens de prompt par seconde, requêtes par seconde.
- **Saturation** : requêtes en cours et en attente, usage du cache KV, préemptions par seconde.
- **Cache de préfixes** : taux de hit = hits / queries.
- **Efficacité** : tokens par seconde et par GPU ; tokens par joule (énergie DCGM) ; part du temps où le GPU est inactif ; coût par million de tokens = (nombre de nœuds GPU × prix horaire) / tokens par heure × 1 000 000. Le prix horaire vient d'un ConfigMap exposé en métrique constante.
- **Routage** : écart de charge entre réplicas.
- **Surcoût des passerelles** : surcoût LiteLLM (`litellm_overhead_latency_metric`, ou latence totale moins latence de l'API LLM) ; durée de décision de l'EPP.

### 12.3 Dashboards

Provisionnés en ConfigMaps (label `grafana_dashboard=1`), rangés par dossiers. Datasources Prometheus, Loki et Alertmanager provisionnées.

À importer puis corriger selon les métriques réelles :

- NVIDIA DCGM Exporter (grafana.com, ID 12239) ;
- dashboards llm-d, dossier `guides/recipes/observability/grafana/dashboards/` du dépôt llm-d : `llm-d-vllm-overview`, `llm-d-failure-saturation-dashboard`, `llm-d-diagnostic-drilldown-dashboard`, `llm-d-performance-kv-cache`, `llm-d-router` ;
- dashboards LiteLLM du dépôt officiel ;
- Istio (plan de contrôle et gateway), KEDA, Argo CD, Loki.

À créer pour le lab, avec les variables `namespace`, `model`, `pod`, `scenario` et les annotations de bench :

1. **00 – Cockpit d'optimisation.** Une ligne par question.
   - Les utilisateurs sont-ils bien servis ? TTFT, inter-token et bout en bout en p50, p95, p99 ; taux d'erreur.
   - Le système sature-t-il ? Requêtes en cours et en attente, temps de file, cache KV, préemptions.
   - Le GPU travaille-t-il ? Utilisation, mémoire, puissance, température, throttling.
   - Est-ce efficace ? Tokens par seconde et par GPU, tokens par joule, coût par million de tokens, part d'inactivité.
   - Le routage est-il bon ? Répartition par pod, taux de hit du cache de préfixes.
   - L'autoscaling suit-il ? Réplicas désirés et prêts, valeur du trigger.
2. **01 – Anatomie d'une requête.** Décomposition du temps : LiteLLM, Gateway, EPP, file vLLM, prefill, decode. Histogrammes en heatmap. Tailles des prompts et des générations.
3. **02 – GPU en profondeur.** Par GPU, nœud et pod : utilisation face à l'activité moteur (profiling), bande passante mémoire, mémoire utilisée et libre, puissance et énergie, température, XID et ECC, PCIe. Corrélation utilisation GPU / tokens par seconde.
4. **03 – Capacité et coût.** Débit maximal observé par scénario, coût horaire, coût par million de tokens, temps GPU inactif, délais de cold start (nœud, image, modèle).
5. **04 – Comparaison de runs.** Avant / après, par annotation : scénario, SHA Git, paramètres vLLM.
6. **05 – Logs.** Loki : erreurs vLLM, événements Kubernetes, access logs de la gateway, alignés sur le temps des métriques.

Chaque panneau porte un titre explicite, une unité et une description : ce qu'il mesure et quel levier d'optimisation il éclaire. Aucun panneau vide sur `baseline-7b` après un bench.

### 12.4 Alertes

`PrometheusRule` + Alertmanager. Chaque alerte porte une annotation `runbook_url` vers `docs/runbooks/<alerte>.md` : symptôme, vérifications, leviers d'optimisation.

- **SLO utilisateur** : TTFT p95 élevé ; latence inter-token p95 élevée ; taux d'erreur ; temps de file p95.
- **Saturation** : requêtes en attente pendant 5 min ; cache KV au-delà de 90 % ; préemptions ; KEDA au maximum avec une file non vide (capacité insuffisante).
- **GPU** : erreur XID ; température ; throttling ; mémoire GPU au-delà de 95 % ; GPU inactif plus de 30 min sur un nœud allumé (coût) ; GPU peu utilisé alors que la file n'est pas vide (le goulot est ailleurs : CPU, tokenisation, réseau).
- **Plateforme** : pod vLLM qui redémarre ou OOM ; cible de scrape absente (vLLM, DCGM, EPP, LiteLLM) ; règles EPP de llm-d (`guides/recipes/observability/alerts/epp-alerting-rules.yaml`) adaptées ; LiteLLM : échecs, déploiement en panne, budget presque épuisé ; application Argo CD dégradée ou désynchronisée ; requêtes corrompues si la métrique existe.

Les seuils vivent dans un fichier de valeurs par scénario. Les seuils SLO sont posés après la première mesure, pas inventés.

Alertmanager : routage par sévérité, regroupement par modèle, inhibition (une cible absente inhibe les alertes SLO correspondantes), récepteur webhook si `ALERT_WEBHOOK_URL` est fourni, sinon récepteur par défaut consultable dans l'interface. Tests unitaires avec `promtool test rules`.

### 12.5 Logs

Loki `Monolithic` (PVC, rétention 7 jours). Alloy en DaemonSet : logs des pods et événements Kubernetes. Labels : `namespace`, `pod`, `container`, `app`, `model`. Logs vLLM en INFO avec les statistiques activées.

### 12.6 Traces (P2, optionnel, désactivé par défaut)

OpenTelemetry vers Tempo, par le champ `spec.tracing` du `LLMInferenceService` et le guide de traçage de llm-d. À ne faire que si tout le reste est vert.

## 13. Banc de charge

inference-perf en outil principal (préfixes partagés, multi-tour, goodput), GuideLLM pour les balayages. Jobs Kubernetes sur le pool système, lancés par `lab.sh bench <profil> [--target litellm|gateway]`.

| Profil | But |
|---|---|
| `smoke` | 10 requêtes, vérifie la chaîne |
| `sweep` | montée en débit jusqu'à saturation : débit maximal sous SLO |
| `steady` | débit constant pendant 10 min |
| `shared-prefix` | préfixe système commun : cache de préfixes et routage |
| `multi-turn` | conversations à contexte croissant |
| `long-prompt` | prompts de 2 000 à 3 500 tokens : stress du prefill (piège B2) |
| `burst` | pic de charge : déclenche KEDA |

Chaque run pose une annotation Grafana de début et de fin (profil, scénario, SHA Git, paramètres vLLM), copie ses résultats JSON dans `results/<date>-<scénario>-<profil>/` et affiche un résumé : TTFT, latence inter-token, tokens par seconde, erreurs, goodput.

## 14. Script `lab.sh`

Idempotent, `set -euo pipefail`, propre à `shellcheck`, logs horodatés, timeouts explicites, codes de retour fiables.

| Commande | Effet |
|---|---|
| `preflight` | outils et versions, session `az`, quota T4, disponibilité du SKU, providers Azure, `.env` |
| `up` | `terraform apply`, kubeconfig, secrets, Argo CD, application racine, attente Synced / Healthy, puis `smoke` |
| `status` | nœuds, GPU alloués, applications Argo CD, `LLMInferenceService`, URLs |
| `smoke` | tests de la section 15 qui ne demandent pas de charge |
| `scenario <nom>` | bascule de scénario par Git |
| `bench <profil>` | lance un profil de charge |
| `ui` | port-forwards Grafana, Prometheus, Alertmanager, Argo CD, LiteLLM ; affiche les identifiants |
| `gpu-scale <0-2>` | nombre de nœuds GPU |
| `stop` / `start` | `az aks stop` / `az aks start`, avec revérification au redémarrage |
| `down` | destruction complète, après confirmation |
| `versions` | versions pinnées et versions réellement déployées |

## 15. Critères d'acceptation

1. `nvidia-smi` répond dans un pod sur chaque T4 ; chaque nœud annonce `nvidia.com/gpu: 1`.
2. Toutes les applications Argo CD sont Synced et Healthy ; une modification manuelle dans le cluster est corrigée par le self-heal.
3. `LLMInferenceService` Ready, `Gateway` Programmed ; un chat completion passe par la Gateway et par LiteLLM (clé virtuelle), en streaming et sans ; le test B5 passe.
4. Toutes les cibles Prometheus attendues sont UP : DCGM, vLLM, EPP, Istio, LiteLLM, KEDA.
5. La jointure GPU / pod vLLM fonctionne (labels du pod sur les métriques DCGM).
6. Aucun panneau vide sur `baseline-7b` après `bench steady`.
7. `promtool` passe ; une alerte de test traverse Alertmanager jusqu'au récepteur ; l'alerte de file d'attente se déclenche sur `bench burst`.
8. Les logs vLLM et les événements Kubernetes sont consultables dans Grafana via Loki.
9. KEDA (`baseline-7b-keda`) : passage de 1 à 2 réplicas sur `bench burst`, retour à 1, délais mesurés.
10. Routage : sur `shared-prefix`, le taux de hit du cache de préfixes est mesuré avec le poids du `prefix-cache-scorer` par défaut puis à 0, et l'écart est consigné.
11. `stop`, `start`, puis `smoke` passent ; `down` ne laisse aucune ressource facturée.
12. Aucun secret dans Git (scan gitleaks).

## 16. Livrables

- Le dépôt Git.
- `README.md` : schéma d'architecture (Mermaid), démarrage en cinq commandes, coûts.
- `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/RUNBOOK.md`, `docs/runbooks/*.md`.
- `docs/METRIQUES.md` : catalogue généré depuis les `/metrics` réels. Pour chaque métrique : nom, type, signification, levier d'optimisation associé.
- `docs/BASELINE.md` :
  - versions exactes déployées et backend d'attention de vLLM ;
  - temps de cold start, étape par étape : nœud, driver, image, téléchargement, chargement ;
  - mémoire GPU par modèle ;
  - résultats `sweep`, `steady`, `shared-prefix` et `long-prompt` pour `baseline-7b` et `small-fp16` : TTFT, latence inter-token, tokens par seconde, débit maximal sous SLO, coût par million de tokens, tokens par joule ;
  - surcoût de LiteLLM et de la Gateway ;
  - comportement de KEDA ;
  - une liste « anomalies et pistes d'optimisation observées », classée par gain potentiel, sans rien appliquer.

## 17. Déroulé

| Phase | Contenu | Coût |
|---|---|---|
| 0 – Cadrage | vérification des versions (`versions.yaml`), questions, plan | gratuit |
| 1 – Dépôt | tout le code ; validations statiques : `terraform validate`, `helm template` + kubeconform, `kustomize build`, `promtool`, `shellcheck` | gratuit |
| Point d'arrêt | résumé, estimation du coût horaire, attente de mon accord | |
| 2 – Infrastructure et GPU | `up` jusqu'à `nvidia-smi` correct et DCGM visible dans Prometheus | payant |
| 3 – Serving | Istio, KServe, scénario `small-fp16` d'abord, puis `baseline-7b` | payant |
| 4 – Passerelle et autoscaling | LiteLLM, KEDA (`baseline-7b-keda`) | payant |
| 5 – Observabilité | dashboards, alertes, logs | payant |
| 6 – Mesures | benchs, `BASELINE.md`, critères d'acceptation, rapport final | payant |

À la fin de chaque phase : un compte rendu court (fait, vérifié, écarts). À la fin du travail, demande-moi si je laisse tourner le cluster ou si tu lances `stop`.

## 18. Références

- KServe, installation llmisvc : https://kserve.github.io/website/docs/install/llmisvc-install
- KServe, configuration : https://kserve.github.io/website/docs/model-serving/generative-inference/llmisvc/llmisvc-configuration
- KServe, référence d'API : https://kserve.github.io/website/docs/reference/crd-api
- KServe v0.21.0 : https://github.com/kserve/kserve/releases/tag/v0.21.0
- KServe, issue Istio et port 9002 : https://github.com/kserve/kserve/issues/5331
- Istio, Inference Extension : https://istio.io/latest/docs/tasks/traffic-management/ingress/gateway-api-inference-extension/
- AKS, GPU Operator : https://learn.microsoft.com/en-us/azure/aks/nvidia-gpu-operator
- NVIDIA, modes GPU sur AKS : https://docs.nvidia.com/aicr/latest/integrator-guide/aks-gpu-setup.md
- vLLM, métriques : https://docs.vllm.ai/en/latest/usage/metrics/
- vLLM, optimisation : https://docs.vllm.ai/en/latest/configuration/optimization/
- vLLM, attention sur T4 : https://github.com/vllm-project/vllm/issues/60821 et https://github.com/vllm-project/vllm/pull/55380
- llm-d, dashboards : https://llm-d.ai/docs/operations/observability/dashboards
- llm-d, alertes : https://llm-d.ai/docs/dev/operations/observability/alerting
- llm-d, requêtes PromQL : https://llm-d.ai/docs/dev/operations/observability/promql
- llm-d sur AKS : https://llm-d.ai/docs/dev/infrastructure/providers/aks
- LiteLLM, Prometheus : https://docs.litellm.ai/docs/proxy/prometheus
- Loki, mode monolithique : https://grafana.com/docs/loki/latest/setup/install/helm/install-monolithic/
- inference-perf : https://github.com/kubernetes-sigs/inference-perf
- Retour d'expérience KEDA + KServe 0.21 : https://github.com/intel/enterprise-inference/pull/67
- Retour d'expérience LLMInferenceService + Istio sur AKS : https://opendatahub-io.github.io/rhaii-on-xks/deploying-rhaii-helmcharts-on-xks-ea2/
