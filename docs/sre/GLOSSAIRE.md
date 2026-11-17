# Glossaire : les mots de l'inférence et de ce cluster

Une ligne par mot, sans jargon inutile. Chaque document du dépôt commence par une petite boîte **« Mots à connaître »** qui reprend seulement les mots dont il se sert ; ici, vous avez tout.
Retour : [README du dépôt](../../README.md) · [guide](../guide/README.md) · [formation](../formation/README.md) · [fiches de services](../services/00-index.md).

**Marques de fiabilité** utilisées dans les docs : **(observé)** = vu sur le cluster ; **(config)** = écrit dans le dépôt ; **(doc)** = tiré de la documentation officielle ;
**(calcul)** = déduit d'un calcul ; **(non vérifié)** = plausible mais pas confirmé.

## Les 12 mots à connaître en premier

| Mot | En une phrase |
|---|---|
| **Inférence** | Faire répondre un modèle déjà entraîné (par opposition à l'entraîner). Ce cluster ne fait que ça. |
| **LLM** | *Large Language Model* : un modèle qui produit du texte, un morceau (token) à la fois. |
| **Token** | Le morceau de texte que le modèle lit et écrit (un mot courant fait environ 1 à 2 tokens). C'est l'unité de tous les calculs. |
| **Prefill** | Première phase : le modèle lit tout le prompt d'un coup. Plus le prompt est long, plus c'est long. |
| **Decode** | Deuxième phase : le modèle écrit la réponse token par token. Plus la réponse est longue, plus c'est long. |
| **Cache KV** | Mémoire où le modèle garde ce qu'il a déjà « compris » du texte, pour ne pas le refaire à chaque token. Il vit dans la mémoire du GPU. |
| **TTFT** | *Time To First Token* : attente avant le premier token de la réponse. C'est ce que l'utilisateur ressent en premier. |
| **TPOT** | *Time Per Output Token* : durée moyenne entre deux tokens de la réponse. C'est la « fluidité » du texte qui s'affiche. |
| **GPU / VRAM** | Le processeur de calcul (ici un NVIDIA T4) et sa mémoire (16 Go). Le modèle et le cache KV doivent y tenir. |
| **vLLM** | Le programme qui charge le modèle sur le GPU et répond aux requêtes. Le « moteur ». |
| **SLO** | Un objectif chiffré de qualité de service, par exemple « 95 % des réponses commencent en moins de 5 s ». |
| **GitOps** | L'état voulu du cluster est écrit dans Git ; Argo CD le fait appliquer. On ne modifie pas le cluster à la main. |

## 1. Le modèle et le texte

| Mot | Définition |
|---|---|
| **Paramètres / poids** | Les nombres appris par le modèle. « 7B » = 7 milliards. Ils sont chargés une fois dans la VRAM. |
| **Prompt** | Le texte envoyé au modèle (question, instructions, documents). |
| **Contexte / `max-model-len`** | Longueur maximale (prompt + réponse) acceptée, en tokens. Ici **4 096**. Au-delà, la requête est refusée (erreur 400). |
| **FP16** | Nombres sur 16 bits (2 octets) : précision normale, modèle plus lourd. C'est le format de calcul utilisé ici (le T4 ne gère pas bf16). |
| **Quantization / AWQ** | Stocker les poids sur 4 bits au lieu de 16 pour réduire la mémoire. Le 7B AWQ pèse **5,29 Gio** (observé) au lieu d'environ 14 (calcul). |
| **Marlin** | Les « petits programmes GPU » (noyaux) qui exécutent les modèles quantizés. |
| **API compatible OpenAI** | Une façon standard de parler à un LLM : `POST /v1/chat/completions`. Tous les composants du lab la parlent. |
| **Streaming** | La réponse arrive token par token au lieu d'un bloc à la fin. |
| **Température** | Réglage du hasard dans le choix des tokens. 0 = réponse reproductible. |

## 2. Ce qui se passe pendant une requête

| Mot | Définition |
|---|---|
| **Batching continu** | vLLM traite ensemble les requêtes en cours, token par token ; une nouvelle requête rejoint le groupe sans attendre la fin des autres. |
| **Attention** | Le calcul qui relie chaque token aux précédents. Il existe plusieurs implémentations (« backends ») ; sur T4 vLLM utilise **Triton** (`TRITON_ATTN`). |
| **Cache de préfixes** | Réutilise le cache KV quand deux requêtes commencent par le même texte (même consigne système). Taux de réussite = *hit ratio*. |
| **Préemption** | Faute de place dans le cache KV, vLLM met une requête de côté et la recalculera plus tard : ça ralentit. |
| **File d'attente** | Requêtes acceptées mais pas encore calculées (`waiting`). `running` = en cours de calcul. Une file qui grossit = capacité dépassée. |
| **Cold start** | Délai entre « on demande un GPU / un pod » et « il répond ». Ici : **721 s** pour un nœud GPU, **~3,5 min** pour changer de modèle (observé). |
| **torch.compile / graphes CUDA** | Optimisations faites au démarrage de vLLM : compiler le modèle et préenregistrer des séquences d'opérations GPU. Elles allongent le démarrage et accélèrent ensuite. |

## 3. Les mesures

| Mot | Définition |
|---|---|
| **Latence de bout en bout** | Durée entre l'envoi et le dernier token de la réponse. |
| **Débit** | Quantité servie par seconde : **req/s** (requêtes) ou **tokens/s** (tokens de sortie). |
| **Percentile (p50, p95, p99)** | p95 = 95 % des requêtes vont plus vite que cette valeur. Le p50 est la médiane. Le p95 montre les cas lents. |
| **Saturation / plateau** | Point où le serveur ne peut plus servir davantage : le débit n'augmente plus et la file grossit. |
| **Boucle ouverte / fermée** | Ouverte : on impose un débit d'arrivée (comme de vrais utilisateurs) ; elle révèle les files. Fermée : N clients attendent chacun leur réponse ; elle masque la surcharge. |
| **Échauffement** | Début de run exclu de la mesure (caches vides, régime pas encore stable). Ici 60 s. |
| **Bruit de mesure / CV** | Variation d'un run à l'autre. CV = écart-type / moyenne. Un écart plus petit que le bruit n'est pas un gain. |
| **Goodput** | Débit des requêtes **réussies et assez rapides** (qui respectent le SLO), pas le débit brut. |
| **Histogramme / seau (bucket)** | Façon de compter les durées par tranches (≤ 1 s, ≤ 2 s, ≤ 5 s...). Les quantiles calculés dessus sont approximatifs. |

## 4. Le GPU

| Mot | Définition |
|---|---|
| **NVIDIA T4** | Le GPU du lab : architecture Turing, 16 Go, 70 W maximum, pas de bf16 ni FP8. Peu cher, peu puissant. |
| **Compute capability** | Numéro de génération d'un GPU (T4 = 7.5). Il décide des fonctions disponibles. |
| **Tensor core** | Unité du GPU spécialisée en multiplications de matrices, très rapide pour l'IA. |
| **SM / warp** | SM : unité de calcul du GPU (le T4 en a 40, doc NVIDIA) ; warp : groupe de 32 threads qui avancent ensemble. |
| **Noyau GPU (kernel)** | Petit programme exécuté sur le GPU. À ne pas confondre avec le noyau Linux du nœud. |
| **DCGM** | Outil NVIDIA qui mesure le GPU ; `dcgm-exporter` publie ces mesures pour Prometheus. |
| **GPU_UTIL** | Part du temps où *au moins un* calcul tournait. **100 % ne veut pas dire saturé** (observé : le même GPU passe de 284 à 933 tokens/s à `GPU_UTIL` constant ou plus bas). |
| **SM_ACTIVE / TENSOR / DRAM_ACTIVE** | Compteurs plus fins : unités de calcul actives / tensor cores actifs / mémoire du GPU active. |
| **Throttling / limite de puissance** | Watts maximum que le GPU peut consommer : 70 W par défaut sur notre T4, réglable de 60 à 70 W (`nvidia-smi -pl`). Quand il l'atteint, le GPU baisse sa fréquence (throttling). |
| **Plafond de puissance (SW power cap)** | Le GPU baisse **lui-même** son horloge pour rester sous sa limite de puissance. C'est le bit `0x4` du masque de bridage : **normal** sous forte charge. |
| **Verrouillage d'horloge** | Fixer la fréquence du GPU (`nvidia-smi -lgc min,max`) ; `-rgc` rend la main au GPU. Sert à mesurer l'énergie par token à chaque fréquence. |
| **Tokens par joule** | Tokens produits pour chaque joule consommé (= tokens par seconde ÷ watts). Mesure d'efficacité énergétique. |
| **dcgmi** | Commande de DCGM : état de santé (`dcgmi health`), diagnostics (`dcgmi diag -r 1/2/3`), injection d'erreurs de test (`dcgmi test --inject`). |
| **XID** | Code d'erreur NVIDIA signalant un problème GPU (ex. 79 : GPU tombé du bus). |
| **ECC / SBE / DBE** | Code qui détecte et corrige les erreurs de la mémoire du GPU. SBE = erreur simple, corrigée ; DBE = erreur double, non corrigeable (grave). |
| **Retrait de pages (page retirement)** | Sur les GPU avant l'A100 (dont le T4), une zone mémoire défaillante est mise de côté définitivement ; le retrait prend effet au redémarrage. |
| **Horloge (clock)** | Fréquence de travail du GPU, en MHz (≈ 585 au repos sur le T4, 1 590 au maximum, relevé par `nvidia-smi -q` sur notre GPU). Elle baisse quand le GPU est bridé. |
| **Raisons de bridage (clock event reasons)** | Les causes qui font baisser l'horloge : repos, plafond de puissance, ralentissement thermique ou matériel... Un masque de bits (`DCGM_FI_DEV_CLOCK_THROTTLE_REASONS`) à décoder. |
| **nvidia-smi** | Commande NVIDIA qui affiche l'état du GPU : température, puissance, horloges, mémoire, erreurs. |
| **Roofline** | Graphique qui dit si un calcul est limité par la mémoire ou par le calcul, selon le nombre d'opérations faites par octet lu. |
| **MFU / MBU** | Part du calcul (MFU) ou de la bande passante mémoire (MBU) réellement utilisée par rapport au maximum du GPU. Le MBU est le bon indicateur du décodage. |
| **DCGM hostengine** | Le processus DCGM qui collecte les mesures du GPU ; l'exporteur peut l'embarquer ou se connecter à un hostengine séparé (doc DCGM). |
| **MIG / MPS / time-slicing** | Trois façons de partager un GPU entre plusieurs programmes (MIG est absent sur T4). |
| **Driver / device plugin** | Pilote du GPU installé sur le nœud / composant qui déclare `nvidia.com/gpu` à Kubernetes. |

## 5. Fiabilité (SRE)

| Mot | Définition |
|---|---|
| **SLI** | L'indicateur mesuré (par exemple : part de requêtes avec un TTFT ≤ 5 s). |
| **SLO** | L'objectif sur cet indicateur, sur une fenêtre (par exemple 95 % sur 30 jours). |
| **Budget d'erreur** | La marge autorisée : 100 % − objectif. SLO à 95 % → 5 % de requêtes lentes tolérées. |
| **Disponibilité** | Part des requêtes qui réussissent (pas d'erreur du côté serveur). |
| **4xx / 5xx** | Codes de réponse HTTP : 4xx = erreur du côté client (requête invalide, contexte trop long) ; 5xx = erreur du côté serveur ; 408 = délai dépassé. |
| **Burn rate** | Vitesse de consommation du budget : 1 = on l'épuise juste à la fin de la fenêtre ; 14,4 = en ~50 h pour une fenêtre de 30 jours. |
| **Méthode USE** | Pour chaque ressource, on regarde l'Utilisation (est-elle occupée ?), la Saturation (y a-t-il de la file ?) et les Erreurs. |
| **Marge (headroom)** | Ce qu'il reste avant une limite : degrés avant la limite thermique, watts avant le plafond de puissance. |
| **Classe de charge** | Un type d'usage avec son propre SLO : interactive, RAG, multi-tour, lot (embeddings non couverte). |
| **RAG** | Question accompagnée de longs documents retrouvés par ailleurs : prompt très long, réponse courte. |
| **Alerte / runbook** | Notification d'un problème / fiche qui dit quoi vérifier et quoi faire (`docs/runbooks/`). |
| **Page / ticket** | Alerte urgente qui doit réveiller quelqu'un / alerte à traiter pendant les heures ouvrées. |
| **Fenêtre glissante** | Période qui avance avec le temps (« les 30 derniers jours »). |
| **promtool** | Outil qui teste les règles Prometheus avec des données fabriquées (`tests/promtool/`). |
| **Game day** | Panne provoquée exprès pour vérifier que le système et l'équipe réagissent bien (pas encore faits ici). |

## 6. Kubernetes et le cluster

| Mot | Définition |
|---|---|
| **Kubernetes / cluster** | Système qui fait tourner des programmes en conteneurs sur plusieurs machines et les maintient en vie. |
| **Nœud / pool de nœuds** | Une machine (VM) du cluster / un groupe de machines identiques. Le lab a un pool « système » et un pool « GPU ». |
| **Pod** | La plus petite unité qui tourne : un ou plusieurs conteneurs. Un pod vLLM = un modèle sur un GPU. |
| **Namespace** | Un « dossier » qui range les objets (`inference`, `gateway`, `monitoring`...). |
| **Deployment / DaemonSet / Job** | Programme à N copies / une copie par nœud / tâche qui se termine (un bench). |
| **Service** | Adresse stable devant un ou plusieurs pods. |
| **ConfigMap / Secret** | Configuration / données sensibles (mots de passe, clés) injectées dans les pods. |
| **Taint / toleration** | « Chasse-pods » posé sur le nœud GPU (`sku=gpu`) / autorisation pour les pods qui doivent y aller. |
| **CRD / opérateur** | Nouveau type d'objet ajouté à Kubernetes / programme qui gère ces objets (ex. `LLMInferenceService`). |
| **Probe (readiness)** | Test qui dit à Kubernetes si un pod est prêt à recevoir du trafic. |
| **AKS** | Kubernetes managé par Azure : Azure gère le « cerveau », vous payez les machines. |
| **PVC / disque persistant** | Demande de stockage qui survit au redémarrage d'un pod (disque managé Azure). Prometheus, Loki et PostgreSQL en ont un. |
| **VMSS** | Groupe de machines virtuelles identiques d'Azure qui se trouve derrière un pool de nœuds. |
| **Terraform** | Décrit l'infrastructure Azure (AKS, pools, secrets) dans des fichiers et la crée ou la détruit : `apply` / `destroy`. |
| **Helm / chart** | Gabarit de manifestes Kubernetes avec des valeurs ; un *chart* = un paquet. |
| **Argo CD / Application** | Applique ce qui est dans Git sur le cluster. Une *Application* = un composant suivi. |
| **Sync wave / self-heal / prune** | Ordre d'application / remet en place toute modification manuelle / supprime ce qui a disparu de Git. |
| **App-of-apps** | Une Application racine qui crée toutes les autres (`gitops/root`). |
| **Scénario** | Un fichier `gitops/scenarios/*.yaml` qui choisit le modèle et les réglages ; un seul est actif. |

## 7. Les composants du lab, en une ligne

| Composant | Rôle |
|---|---|
| **vLLM** | Charge le modèle sur le GPU et génère les réponses. |
| **llm-d / EPP** | *Endpoint Picker* : choisit le pod vLLM le mieux placé (peu chargé, cache de préfixes) pour chaque requête. |
| **KServe / `LLMInferenceService`** | Un seul objet déclare un modèle ; KServe crée les pods, le routage et le choix du pod. |
| **Gateway API / GIE / Istio** | Standard de routage HTTP / son extension pour l'inférence / l'implémentation qui fait tourner la Gateway (Envoy). |
| **LiteLLM** | Passerelle OpenAI-compatible : clés virtuelles, budgets, limites, métriques par client. |
| **KEDA** | Ajoute ou retire des pods selon la file d'attente de vLLM. |
| **GPU Operator** | Installe le driver NVIDIA et ses outils sur les nœuds GPU. |
| **Prometheus / Alertmanager** | Stocke les métriques / envoie les alertes. |
| **Grafana / Loki / Alloy** | Tableaux de bord / stockage des logs / agent qui collecte les logs. |
| **Bench (inference-perf)** | Génère de la charge pour mesurer. |
| **Clé virtuelle** | Clé d'API LiteLLM par client ; l'alias de la clé sert ici à identifier la **classe de charge**. |
| **Pré-tirage d'image (`image-prepull`)** | Télécharge l'image vLLM (~9 Go) sur le nœud GPU avant qu'on en ait besoin. |

## 8. Observabilité

| Mot | Définition |
|---|---|
| **Métrique** | Un nombre mesuré dans le temps (ex. `vllm:num_requests_waiting`). *Counter* = ne fait que monter ; *gauge* = monte et descend. |
| **Scrape / cible** | Prometheus interroge périodiquement chaque programme exposant `/metrics`. |
| **PromQL** | Langage de requête de Prometheus. |
| **Recording rule** | Requête PromQL précalculée et enregistrée comme nouvelle métrique (nom en `lab:` ou `slo:`). |
| **Dashboard / panneau / annotation** | Page Grafana / un graphique / un repère de temps (début et fin d'un bench). |
| **ServiceMonitor / PrometheusRule** | Objets qui déclarent à Prometheus quoi scruter / quelles règles et alertes appliquer. |

## 9. Sécurité et identités

| Mot | Définition |
|---|---|
| **Authentification** | Prouver qui on est (mot de passe, clé d'API, certificat, jeton). |
| **ServiceAccount / jeton** | L'identité d'un programme dans Kubernetes et le « badge » temporaire qu'il présente à l'API. |
| **RBAC / ClusterRole** | Les droits donnés à une identité (par exemple « lire les pods »). Un *ClusterRole* vaut pour tout le cluster. |
| **TLS / mTLS** | Chiffrement d'un échange ; en *mTLS* les deux côtés prouvent aussi leur identité. |
| **NetworkPolicy** | Règle Kubernetes qui limite qui peut parler à qui. Le lab n'en a presque pas. |
| **Digest d'image** | Empreinte exacte d'une image de conteneur : on « épingle » la version au lieu d'un tag qui peut changer. |
| **Webhook** | Adresse HTTP qui reçoit des messages d'un autre programme (ici : les alertes d'Alertmanager). |
