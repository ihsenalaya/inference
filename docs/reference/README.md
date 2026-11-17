# Références : photos du cluster

Ces fichiers sont des **captures brutes** du cluster réel (16/11/2026, 7B AWQ, 2 nœuds GPU), prises avant sa destruction. Ils ne sont pas rédigés : ce sont des preuves auxquelles les autres documents renvoient quand ils écrivent **(observé)**.
Si vous débutez, lisez d'abord le [guide](../guide/README.md) ; ouvrez ces fichiers seulement pour vérifier un détail. Les mots : [glossaire](../sre/GLOSSAIRE.md).

| Fichier | Ce que c'est | À quoi ça sert |
|---|---|---|
| [workloads.txt](workloads.txt) | La liste de tous les programmes qui tournent (pods, images, ressources demandées, ports, identités) | Savoir qui tourne où, avec quelles ressources |
| [services.txt](services.txt) | Les adresses internes (Services) et leurs ports | Connaître les ports (ex. 4000 LiteLLM, 9002 EPP) |
| [routing.yaml](routing.yaml) | La Gateway, la route HTTP et le pool d'inférence créés pour un modèle | Voir comment une requête est aiguillée (`/inference/<modèle>/...` -> pool + EPP) |
| [llminferenceservice.yaml](llminferenceservice.yaml) | L'objet `LLMInferenceService` d'un modèle, tel que le cluster le voit | Voir tout ce que KServe a déduit d'un seul objet déclaré |
| [crd-groups.txt](crd-groups.txt) | Les nouveaux types d'objets ajoutés à Kubernetes (CRD) | Savoir quels composants ont étendu Kubernetes |

Ces captures sont **datées** : elles ne suivent pas les changements du 17/11 (par exemple les 4 clés de classe de charge LiteLLM, le DaemonSet de pré-tirage ou les 21 Applications Argo CD).

## Captures de la séance GPU (17/11/2026)

Les sorties brutes de la séance GPU sont dans [`results/session-gpu-2026-11-17/`](../../results/session-gpu-2026-11-17/) (et non ici, car elles sont nombreuses et volumineuses) ; le [chapitre 07 du dossier GPU](../gpu/07-resultats-seance.md) dit lesquelles lire :

| Dossier | Contenu |
|---|---|
| `nvidia-smi/` | `nvidia-smi -q` par section (horloges acceptées, puissance, températures, ECC, pages retirées, bridage), topologie, version du pilote |
| `dcgm/` | toutes les sorties de `dcgmi` (découverte, groupes, santé, `diag -r 1/2/3` avec vLLM chargé puis GPU libre, `dmon`, injection d'un XID 79) |
| `prometheus/` | catalogue des 3 885 noms de métriques, état des 359 règles, séries du GPU toutes les 15 s (`series-gpu.csv`), métriques brutes de l'exporteur, alertes finales |
| `cluster/` | nœud GPU (labels, capacités), pods, applications Argo CD, ClusterPolicy du GPU Operator, journaux de vLLM, de l'exporteur et du récepteur d'alertes, événements |
