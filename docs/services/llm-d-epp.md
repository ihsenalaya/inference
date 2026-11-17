# EPP llm-d (Endpoint Picker) - le routeur d'inférence

**En une phrase.** L'EPP est l'« aiguilleur intelligent » : pour chaque requête, il choisit quel pod vLLM la traitera, en regardant lequel est le moins chargé et lequel a déjà le début du texte en mémoire.

<!-- mots: epp, cache de préfixes, cache kv, file d'attente, tls, serviceaccount -->
> **Mots à connaître**
> - **llm-d / EPP** : *Endpoint Picker* : choisit le pod vLLM le mieux placé (peu chargé, cache de préfixes) pour chaque requête.
> - **Cache de préfixes** : Réutilise le cache KV quand deux requêtes commencent par le même texte (même consigne système). Taux de réussite = *hit ratio*.
> - **Cache KV** : Mémoire où le modèle garde ce qu'il a déjà « compris » du texte, pour ne pas le refaire à chaque token. Il vit dans la mémoire du GPU.
> - **File d'attente** : Requêtes acceptées mais pas encore calculées (`waiting`). `running` = en cours de calcul. Une file qui grossit = capacité dépassée.
> - **TLS / mTLS** : Chiffrement d'un échange ; en *mTLS* les deux côtés prouvent aussi leur identité.
> - **ServiceAccount / jeton** : L'identité d'un programme dans Kubernetes et le « badge » temporaire qu'il présente à l'API.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Rôle
Un **routeur intelligent** : parmi les pods vLLM d'un pool, il choisit **celui qui servira chaque requête**, au lieu d'un simple tour de rôle. Il est livré avec KServe (image `ghcr.io/llm-d/llm-d-router-endpoint-picker:v0.10.0`), un par `LLMInferenceService`
(Deployment `<nom>-kserve-router-scheduler`, Service `<nom>-epp-service`).

## Pourquoi c'est utile pour l'inférence
Deux requêtes ne coûtent pas la même chose : une requête dont le **préfixe est déjà en cache** sur un pod est beaucoup moins chère à y envoyer (cf. [guide inférence §6](../guide/01-inference-expliquee.md)), et un pod dont la file est longue ou le cache KV plein est un mauvais choix.
Un répartiteur HTTP classique ignore tout cela.

## Place dans l'architecture
Envoy (Gateway) l'appelle en **ext_proc** (le mécanisme qui lui délègue la décision ; gRPC) pour chaque requête d'inférence ; l'EPP répond « envoie-la à tel pod ». Il tourne sur le pool **système**.

## Relations
- **Appelé par** : la Gateway Istio (gRPC :9002, TLS auto-signé).
- **Lit** : l'API Kubernetes (pods, `InferencePool`, EndpointSlices = listes d'adresses de pods) pour connaître les membres du pool ; **scrape les métriques de chaque pod vLLM** (file, cache KV, requêtes en cours, cache de préfixes) pour décider.
- **Scrapé par** : Prometheus (port 9090, jeton requis).

## Configuration retenue
Ports (observé) : `9002` gRPC ext_proc, `9003` santé gRPC, `9090` métriques, `5557` zmq (ZeroMQ, une bibliothèque de messagerie interne ; usage exact non vérifié). Arguments : `--pool-name <nom>-inference-pool --pool-namespace inference --grpc-port 9002 --grpc-health-port 9003 --zap-encoder json`.
Ressources : le preset demandait 1 CPU / 2 Gi (limite 6 CPU / 16 Gi) ; nous les surchargeons à **100 m / 256 Mi (limite 1 Gio)** (`scheduler.resources`) pour tenir sur le nœud système.

Configuration de routage = `EndpointPickerConfig` (preset `kserve-config-llm-scheduler-eppconfig-default`, observé) :
- plugins : `approx-prefix-cache-producer`, `inflight-load-producer`, `prefix-cache-affinity-filter`, `token-load-scorer` ;
- profil `default` : `prefix-cache-affinity-filter` (filtre : privilégie les pods qui ont déjà le préfixe) puis `token-load-scorer` (score : évite les pods chargés en tokens).
- Variante d'expérience `epp.loadOnly` (`gitops/serving/chart`) : profil sans filtre d'affinité (charge seule), utilisée pour mesurer l'apport du cache de préfixes.

`failureMode: FailOpen` du pool : si l'EPP tombe, la Gateway **laisse passer** la requête vers le service (comportement à tester par un game day).

## Authentification
- **Vers l'API** : ServiceAccount `<nom>-epp-sa` ; Role : lecture `pods`, `inferencepools`, `inferenceobjectives`, `inferencemodelrewrites`, `endpointslices` ; écriture `leases`, `events`.
- **Ses clients** : un `ClusterRoleBinding` donne à son SA `system:auth-delegator` (TokenReview/SubjectAccessReview) : l'EPP **authentifie et autorise** ceux qui lisent son `/metrics` -> Prometheus doit présenter un jeton de ServiceAccount (**observé** : HTTP 401 sinon).
- Côté gRPC 9002 : TLS auto-signé ; les clients (Envoy) ne vérifient pas le certificat.

## Données traitées
Les **en-têtes et le corps** de chaque requête (il lit le modèle demandé ; pour l'affinité de préfixes il s'appuie sur le contenu du prompt - mécanisme exact non vérifié ici : voir la doc du scheduler llm-d) et les **métriques de chaque pod**. Mémoire : table d'index de préfixes (`llm_d_epp_prefix_indexer_*`).

## Contribution à l'inférence
- **Équilibrage** : sur 2 réplicas, 277 / 299 requêtes (observé) : charge équilibrée.
- **Affinité de préfixes** : taux de hit du cache vLLM 97,9-98,1 % avec le profil par défaut contre 95,4-96,4 % en charge seule (observé) : gain faible avec seulement 4 préfixes qui tiennent dans le cache des deux pods ; l'écart devrait grandir avec plus de préfixes que n'en contient un cache.
- Le choix du pod est pris **par requête**, avant tout calcul : l'EPP ne peut pas réparer un pod saturé, il peut seulement envoyer les requêtes ailleurs.

## Métriques à suivre (observé : deux familles coexistent)
`llm_d_epp_ready_endpoints`, `llm_d_epp_per_endpoint_queue_size`, `llm_d_epp_average_kv_cache_utilization`, `llm_d_epp_std_dev_queue_size` (déséquilibre), `llm_d_epp_request_ttft_seconds`, `llm_d_epp_request_total` (+ erreurs), `llm_d_epp_plugin_duration_seconds` / `inference_extension_scheduler_e2e_duration_seconds` (temps de décision), `llm_d_epp_prefix_indexer_hit_ratio`.
Alertes importées de llm-d : `EPPHighErrorRatio`, `EPPNoReadyEndpoints`, `EPPMetricsAbsent`, `EPPDataLayerPollErrors`, `EPPExtProcStreamErrors`...

## Pannes et diagnostic
| Symptôme | Cause |
|---|---|
| HTTP 500 sur toutes les requêtes d'inférence | TLS Envoy -> EPP (`DestinationRule` manquante) |
| `EPPNoReadyEndpoints` | aucun pod vLLM prêt (démarrage ou panne) |
| cible `lab-epp` en 401 | jeton de scrape absent |
| Redémarrages de l'EPP | à surveiller ; logs JSON (`zap`) |
