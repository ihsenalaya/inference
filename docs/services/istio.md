# Istio (istiod) et la Gateway d'inférence

**En une phrase.** Ici Istio ne sert qu'à fabriquer et piloter la porte d'entrée HTTP (un proxy Envoy) devant les modèles ; ce n'est pas utilisé comme « maillage de services ».

<!-- mots: gateway api, epp, tls, service -->
> **Mots à connaître**
> - **Gateway API / GIE / Istio** : Standard de routage HTTP / son extension pour l'inférence / l'implémentation qui fait tourner la Gateway (Envoy).
> - **llm-d / EPP** : *Endpoint Picker* : choisit le pod vLLM le mieux placé (peu chargé, cache de préfixes) pour chaque requête.
> - **TLS / mTLS** : Chiffrement d'un échange ; en *mTLS* les deux côtés prouvent aussi leur identité.
> - **Service** : Adresse stable devant un ou plusieurs pods.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

## Rôle
Deux éléments distincts :
1. **istiod** (plan de contrôle) : lit les objets Gateway API et **configure Envoy** ; v1.30.8.
2. La **Gateway** `inference-gateway` : un déploiement **Envoy** (`proxyv2:1.30.8`) créé automatiquement par istiod à partir de l'objet `Gateway` (classe `istio`). C'est le **point d'entrée de l'inférence**.

Istio n'est **pas** utilisé comme service mesh (réseau de proxys autour de chaque pod) : pas de sidecar (proxy ajouté à chaque pod), pas de mTLS automatique (chiffrement mutuel entre pods) (label `sidecar.istio.io/inject: false` sur les pods de la Gateway).

## Place dans l'architecture
`LiteLLM -> Gateway (Envoy) -> EPP (ext_proc) -> pod vLLM`. La Gateway est dans le namespace `inference`, Service `inference-gateway-istio` (ClusterIP, port 80 ; l'annotation `networking.istio.io/service-type: ClusterIP` évite le LoadBalancer).

## Relations
- Reçoit les requêtes de LiteLLM (HTTP).
- Lit les `HTTPRoute` créées par KServe ; appelle l'**EPP** par `ext_proc` (le mécanisme qui lui délègue le choix du pod ; gRPC + TLS) ; transmet au pod choisi.
- Exporte ses métriques à Prometheus (`:15090`, `/stats/prometheus`) et ses **access logs JSON** sur stdout (collectés par Alloy -> Loki).

## Configuration retenue (config : `gitops/platform/istiod/values.yaml`, `gitops/gateway/inference-gateway`)
- Chart Helm `istiod` seul (le profil « minimal » n'existe que pour `istioctl` : le chart `istiod` suffit).
- Variables de pilot : `SUPPORT_GATEWAY_API_INFERENCE_EXTENSION=true`, `ENABLE_GATEWAY_API_INFERENCE_EXTENSION=true`.
- `meshConfig` : `accessLogFile: /dev/stdout`, `accessLogEncoding: JSON`, `proxyStatsMatcher` ouvert (`.*`), Prometheus merge activé.
- **`DestinationRule` par modèle** (`gitops/serving/chart/templates/epp-tls.yaml`) : hôte `<modèle>-epp-service`, TLS `SIMPLE` avec `insecureSkipVerify: true`. Indispensable : l'EPP sert son gRPC en TLS auto-signé ; sans cette règle Envoy parle en clair -> `ext_proc_error_gRPC_error_14`, HTTP 500 (**observé**).
- Timeouts de route : `request: 0s` et `backendRequest: 0s` (aucun timeout) dans les routes générées par KServe (**observé**) : les générations longues ne sont pas coupées, mais une requête bloquée ne l'est pas non plus.
- Limite du pod Envoy : requests 100 m / 128 Mi, limite CPU 2, mémoire 1 Gio (observé).

## Authentification
Aucune authentification des appelants au niveau de la Gateway ; pas de `PeerAuthentication` ni de `AuthorizationPolicy` (observé). Le lien Envoy -> EPP est chiffré mais le certificat n'est pas vérifié.

## Données traitées
Le **contenu intégral des requêtes et réponses** (prompts, tokens générés) transite en clair dans Envoy ; l'EPP en reçoit les en-têtes et le corps. Les access logs contiennent chemin, code, durées, upstream (pas le corps).

## Contribution à l'inférence
Aiguillage : choix du modèle par le chemin (`/inference/<modèle>/...`), réécriture du chemin vers `/v1/...`, délégation du **choix du pod** à l'EPP. Ajoute une latence de quelques millisecondes (non isolée précisément : l'écart LiteLLM vs Gateway directe est de +25 à +50 ms au total, dont la part d'Istio est inconnue).

## Métriques à suivre
`istio_requests_total{response_code}`, `istio_request_duration_milliseconds_bucket`, `envoy_cluster_upstream_rq_time_*`, `envoy_cluster_upstream_rq_timeout`. Logs : `{namespace="inference", container="istio-proxy"}` avec `response_code_details` (cause des erreurs).

## Pannes et diagnostic
| Symptôme | Cause |
|---|---|
| HTTP 500, `ext_proc_error_gRPC_error_14 ... connection termination` | pas de `DestinationRule` TLS vers l'EPP |
| `Programmed: False` sur la Gateway | lire les logs d'istiod ; CRDs Gateway API absentes au démarrage d'istiod |
| `istiod` : `unknown profile minimal` | profil `istioctl` utilisé dans les valeurs Helm (corrigé) |
| Charts Istio 1.31/1.32 introuvables | non publiés dans le dépôt Helm (404 constaté le 16/11/2026) : version épinglée à 1.30.8 |
