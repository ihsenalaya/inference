# Gateway API et Gateway API Inference Extension (CRDs)

## Rôle
Ce ne sont **pas des programmes** mais des **définitions d'objets** (CRDs) qui donnent un vocabulaire standard au routage :

| Définition | Objets | Rôle |
|---|---|---|
| **Gateway API** v1.5.1 (canal standard) | `GatewayClass`, `Gateway`, `HTTPRoute`... | décrire un point d'entrée HTTP et ses règles de routage |
| **GIE** (Gateway API Inference Extension) v1.5.0 | `InferencePool` (+ objets alpha : `InferenceObjective`, `InferenceModelRewrite`) | décrire un **pool de pods d'inférence** et l'**EPP** qui choisit entre eux |

## Place dans l'architecture
Installées en **vague 0** (avant tout). Gateway API : `gitops/platform/crds-gateway-api` (manifeste officiel `standard-install.yaml`). GIE : `gitops/platform/crds-gie` (kustomize `config/crd?ref=v1.5.0`).
Les versions sont celles **imposées par KServe v0.21.0** (`kserve-deps.env`). Elles doivent exister **avant istiod**, sinon istiod ne les voit pas (piège C1 du prompt d'origine).

## Relations
- Istio (istiod) implémente `Gateway`/`HTTPRoute` et, avec ses variables `ENABLE_GATEWAY_API_INFERENCE_EXTENSION`, le comportement d'`InferencePool`.
- KServe crée les `HTTPRoute` et `InferencePool` pour chaque modèle.
- L'EPP lit les `InferencePool`.

## Configuration retenue
Aucune : manifestes officiels. Le chart KServe `kserve-llmisvc-resources` est configuré avec `createGIECRDs: false` pour ne pas installer les CRDs GIE une seconde fois.

## Authentification / données
Sans objet (définitions).

## Contribution à l'inférence
Elles rendent possible le **routage conscient de l'inférence** : l'`InferencePool` déclare `endpointPickerRef` (le Service de l'EPP, port 9002, `failureMode: FailOpen`) :
si l'EPP est indisponible, la Gateway **laisse passer** les requêtes (pas de refus) - c'est le mode `FailOpen` (**observé** dans la spec du pool). Le comportement exact en panne de l'EPP reste à tester (game day prévu).

## Pannes
CRD absente = les composants qui en dépendent échouent à la synchro (puis réussissent aux réessais).
