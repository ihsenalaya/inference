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
