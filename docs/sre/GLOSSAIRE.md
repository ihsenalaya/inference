# Glossaire

Définitions courtes, orientées inférence et ce cluster. Renvois : [guide](../guide/README.md), [fiches de services](../services/00-index.md).

## Inférence

| Terme | Définition |
|---|---|
| **Token** | morceau de texte (mot, partie de mot, ponctuation) : l'unité que le modèle lit et produit. |
| **Prompt / prefill** | le texte d'entrée ; le **prefill** est le calcul qui le traite d'un coup et remplit le cache KV. Limité par le calcul. |
| **Decode** | génération des tokens un par un ; chaque étape relit les poids. Limité par la bande passante mémoire (petit batch). |
| **TTFT** | *time to first token* : délai jusqu'au premier token. Dominé par la file d'attente et le prefill. |
| **TPOT / ITL** | temps par token de sortie (moyenne par requête) / délai entre deux tokens consécutifs. |
| **Cache KV** | clés et valeurs d'attention gardées en VRAM pour ne pas recalculer le contexte. 57 344 octets par token pour Qwen2.5-7B (calcul). |
| **Batching continu** | à chaque étape, vLLM regroupe un token de chaque requête en cours ; le groupe change en continu. |
| **Cache de préfixes** | réutilise le cache KV de préfixes identiques entre requêtes (prompt système, document). |
| **Préemption** | vLLM évince une requête faute de place dans le cache KV ; elle sera recalculée. |
| **Quantization (AWQ)** | poids stockés sur 4 bits au lieu de 16 : modèle ~3x plus petit en mémoire. |
| **Marlin** | famille de noyaux GPU qui exécutent les modèles quantizés (utilisée ici pour AWQ). |
| **Attention** | calcul qui relie chaque token aux précédents ; son implémentation (backend) change beaucoup les performances. |
| **TRITON_ATTN / FlashAttention / FlashInfer** | backends d'attention de vLLM ; sur T4 seul Triton est disponible, sans tensor cores. |
| **Boucle ouverte / fermée** | ouverte : débit d'arrivée imposé (révèle les files) ; fermée : concurrence fixe (masque les files). |
| **Goodput** | débit des requêtes qui respectent le SLO. |
| **Saturation / genou** | point où le débit servi n'augmente plus alors que la charge demandée augmente (la file s'allonge). |
| **Loi de Little** | requêtes en vol = débit x latence. |
| **SLI / SLO / budget d'erreur / burn rate** | indicateur mesuré / objectif sur cet indicateur / marge d'écart autorisée / vitesse à laquelle on consomme cette marge. |

## GPU

| Terme | Définition |
|---|---|
| **VRAM** | mémoire du GPU (16 Go sur T4) : poids + cache KV + activations. |
| **Compute capability** | version d'architecture du GPU (T4 = 7.5, Turing). Conditionne les fonctionnalités (pas de bf16/FP8/FlashAttention 2 avant 8.0). |
| **Tensor core** | unité de calcul spécialisée en multiplication de matrices. |
| **MIG / MPS / time-slicing** | trois façons de partager un GPU : partition matérielle (absente sur T4) / exécution concurrente / tranches de temps. |
| **DCGM** | outil NVIDIA de télémétrie GPU ; *dcgm-exporter* le publie en métriques Prometheus. |
| **GPU_UTIL vs ENGINE_ACTIVE vs DRAM_ACTIVE** | rapport cyclique « un noyau tourne » / occupation du moteur graphique / activité de la mémoire. |
| **XID** | code d'erreur NVIDIA remonté par le driver (ex. 79 : GPU tombé du bus). |
| **Throttling** | le GPU baisse ses fréquences (puissance ou température). |
| **Driver / toolkit / device plugin** | pilote noyau / configuration du runtime de conteneurs / annonce de `nvidia.com/gpu` à kubelet. |

## Kubernetes, GitOps et plateforme

| Terme | Définition |
|---|---|
| **AKS** | Kubernetes managé d'Azure. **Pool de nœuds** : groupe de VM identiques (VMSS). |
| **Taint / toleration** | marque qui repousse les pods (`sku=gpu:NoSchedule`) / autorisation d'y aller. |
| **CRD** | définition d'un nouveau type d'objet Kubernetes. |
| **Argo CD / GitOps** | l'état du cluster est décrit dans Git ; Argo CD le réconcilie en continu. **Sync wave** : ordre de création. **Self-heal** : annule les modifications manuelles. |
| **App-of-apps** | une Application racine qui génère les autres. |
| **Helm / Kustomize** | moteurs de modèles de manifestes. |
| **Gateway API** | standard Kubernetes de routage HTTP (`Gateway`, `HTTPRoute`). |
| **GIE / InferencePool** | extension Gateway API pour l'inférence ; un `InferencePool` = pool de pods + l'EPP qui choisit. |
| **EPP** | *Endpoint Picker* : service gRPC qui choisit le pod pour chaque requête. **ext_proc** : filtre Envoy qui lui délègue la décision. |
| **KServe / LLMInferenceService** | plateforme de serving ; objet déclaratif qui crée tout le serving d'un LLM. **Preset** : modèle de configuration réutilisable. |
| **KEDA / HPA / ScaledObject** | autoscaling par métriques externes / autoscaler horizontal Kubernetes / objet KEDA qui décrit le signal. |
| **Istio / Envoy** | mesh de services (ici seulement l'implémentation de la Gateway) / proxy réseau. |
| **LiteLLM / clé virtuelle** | proxy OpenAI-compatible / clé d'API gérée par LiteLLM, rattachée à une équipe avec budget et limites. |
| **Cold start** | durée entre « un nœud/pod est demandé » et « il sert des requêtes ». |
| **PVC / StorageClass** | demande de volume persistant / type de stockage (disque managé Azure). |
| **ServiceMonitor / PodMonitor / PrometheusRule** | objets de l'opérateur Prometheus : cibles de scrape, règles. |
| **Recording rule** | requête PromQL précalculée et stockée comme nouvelle série (`lab:*`). |
| **Annotation Grafana** | repère temporel affiché sur les dashboards (début/fin de bench). |
