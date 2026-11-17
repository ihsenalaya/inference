# Module 6 - Le démarrage à froid : où va le temps, et ce qu'on a gagné

**En une phrase.** Un GPU coûte de l'argent dès qu'il existe, même quand il ne répond à personne : ce module décompose tout ce qu'il faut attendre avant qu'un modèle serve, et montre ce qu'on a gagné.

<!-- mots: cold start, driver, daemonset, argo cd, sync wave, terraform, torch.compile -->
> **Mots à connaître**
> - **Cold start** : Délai entre « on demande un GPU / un pod » et « il répond ». Ici : **721 s** pour un nœud GPU, **~3,5 min** pour changer de modèle (observé).
> - **Driver / device plugin** : Pilote du GPU installé sur le nœud / composant qui déclare `nvidia.com/gpu` à Kubernetes.
> - **Deployment / DaemonSet / Job** : Programme à N copies / une copie par nœud / tâche qui se termine (un bench).
> - **Argo CD / Application** : Applique ce qui est dans Git sur le cluster. Une *Application* = un composant suivi.
> - **Sync wave / self-heal / prune** : Ordre d'application / remet en place toute modification manuelle / supprime ce qui a disparu de Git.
> - **Terraform** : Décrit l'infrastructure Azure (AKS, pools, secrets) dans des fichiers et la crée ou la détruit : `apply` / `destroy`.
> - **torch.compile / graphes CUDA** : Optimisations faites au démarrage de vLLM : compiler le modèle et préenregistrer des séquences d'opérations GPU. Elles allongent le démarrage et accélèrent ensuite.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

**Objectif** : savoir décomposer le démarrage d'un cluster d'inférence, lire chaque étape dans les objets Kubernetes,
et juger un « gain » avec des chiffres comparables. Marques de fiabilité : voir [le guide](../guide/README.md).

## 1. Pourquoi c'est un sujet d'inférence et pas seulement d'infrastructure

Un pod vLLM n'est utile qu'une fois : le nœud GPU créé, le **driver NVIDIA** compilé, le **plugin GPU** annoncé, le **modèle** téléchargé,
l'**image** (~9 Go) tirée, puis le moteur chargé (poids, `torch.compile`, graphes CUDA). Tant que ce n'est pas fini, **le GPU est facturé
sans servir personne** : 0,526 $/h pour le T4 (calcul : prix catalogue retenu dans `gpuHourlyPrice`). Quand KEDA ajoute un réplica
sous la charge, c'est ce délai que vos utilisateurs subissent (module 7 des séances d'autoscaling, A3 dans le plan).

## 2. La chaîne, mesurée (observé)

Outil : `tests/coldstart.py` (lit les horodatages des objets Kubernetes et les logs de vLLM). Deux installations complètes depuis un
groupe de ressources vide, **sans aucune action manuelle** :

| Étape | Install. A (16-17/11, avant les changements) | Install. B (17/11, après) | Écart |
|---|---|---|---|
| Nœud GPU créé -> driver NVIDIA démarré | 590 s | **317 s** | -273 s |
| Compilation des modules noyau du driver | 191 s | 221 s | +30 s (bruit) |
| Nœud GPU créé -> GPU annoncé (`nvidia.com/gpu`) | 804 s | **564 s** | -240 s |
| Pod planifié -> modèle téléchargé | 41 s (7B AWQ, 5,3 Gio) | 24 s (1,5B FP16, 3 Gio) | modèle différent |
| Modèle téléchargé -> conteneur vLLM démarré (pull de l'image) | 215 s | **1 s** | -214 s |
| Conteneur démarré -> Ready | 154 s | 115 s | modèle différent |
| **Nœud GPU créé -> vLLM Ready** | **1228 s** | **721 s** | **-507 s (-41 %)** |

Attention à la comparaison : **le modèle n'est pas le même** (7B AWQ en A, 1,5B FP16 en B). Les écarts « modèle téléchargé » et « conteneur ->
Ready » dépendent de la taille du modèle ; on ne les attribue donc pas aux changements. Les deux gains **attribuables** à ces changements sont
les lignes 1 et 4 : **-273 s** et **-214 s**, soit **-487 s** sur les -507 s observés (le reste vient du modèle plus petit).

## 3. Les deux changements qui ont produit ce gain (config)

1. **GPU Operator en vague 1 d'Argo CD** (`gitops/root/values.yaml`). Avant, il attendait derrière cert-manager et la pile Prometheus
   (vague 3) : le driver ne démarrait que ~10 min après la création du nœud. Maintenant il démarre en parallèle (**317 s** au lieu de 590 s ;
   ces 317 s restants sont le temps pour qu'Argo CD (lui-même installé par Terraform) atteigne la vague 1 et que le DaemonSet soit
   planifié : **cause non décomposée plus finement**).
2. **Pré-tirage de l'image vLLM** (`gitops/platform/image-prepull`, DaemonSet sur le pool GPU, même digest que le serving ; un test
   statique vérifie que les deux digests sont identiques). L'image de ~9 Go est tirée pendant que le driver compile, au lieu de
   l'être après le téléchargement du modèle.

## 4. Le temps total d'un `lab.sh up`

| Mesure | Valeur | Remarque |
|---|---|---|
| Début de Terraform | 07:38:02 UTC | |
| `terraform apply` terminé | 530 s (cluster AKS 4 min 8) | contre 575 s (A) |
| Toutes les applications Argo CD Healthy | **07:55:59 UTC (17 min 57 s)** | lu dans `operationState.finishedAt` des 21 applications |
| Pod vLLM Ready | **07:56:57 UTC (18 min 55 s)** | contre **28 min 46 s** en A (7B) |

Honnêteté sur cette mesure : le script `lab.sh up` s'est **arrêté** pendant l'attente (le lien `/usr/local/bin/kubectl` pointait vers un
Docker Desktop arrêté, erreur d'entrée/sortie ; `set -e` a tué le script sans message). Il a été relancé (idempotent, 51 s) et le smoke
est passé 9/9. Les durées ci-dessus sont reconstruites **à partir des horodatages Kubernetes**, pas du chronomètre du script. L'écart avec A
(-9 min 51 s) mélange la baisse due aux deux changements et la différence de modèle (quelques dizaines de secondes).

## 5. Ce qui reste sur le chemin critique

À 07:55:59 tout est sain, mais le pod vLLM n'est prêt qu'à 07:56:57. Les ~19 minutes se décomposent ainsi (horodatages) : le nœud GPU est créé à 07:44:56 (6 min 54 s après le début de Terraform), puis il faut
**12 min** (721 s) pour qu'il ait un driver, un plugin, un modèle et un pod vLLM prêt.
Les pistes qui restent :

- le **driver** (221 s de compilation de modules noyau à chaque nouveau nœud) : un nœud préconfiguré ou une image avec le driver
  pré-installé supprimerait cette étape (non testé) ;
- le **moteur** vLLM (115 s pour le 1,5B, 154 s pour le 7B) : cache de compilation persistant (A3 du plan, non testé) ;
- la **création de l'AKS** elle-même (~4 min), incompressible.

## 6. Ce qu'il faut retenir

1. Mesurer **chaque** étape avant de la « réparer » : la plus grosse (le driver qui attendait) n'était pas là où on l'attendait (le modèle).
2. Un changement d'ordre (vague 3 -> vague 1) a coûté une ligne de YAML et valu **273 s par nouveau nœud GPU**, soit 0,04 $ de T4 à chaque
   démarrage... et surtout 4,5 min de moins d'attente pour chaque réplica ajouté par l'autoscaling.
3. Une comparaison n'est honnête que si une seule variable change : ici le modèle a changé, donc seules deux lignes sont attribuables.

## 7. Exercice (à faire vous-même)

Objectif : retrouver les durées « nœud créé -> driver démarré » et « conteneur démarré -> Ready » sur **votre** prochaine installation,
sans lire la solution ci-dessus.
- Lancez `python3 tests/coldstart.py` (avec `KUBECONFIG` sur le cluster).
- Dites quelle étape est la plus longue, et laquelle vous réduiriez en premier avec un budget d'une heure de travail.
Vérification : comparez avec la table du §2 ; si une étape diffère de plus de 30 %, cherchez pourquoi avant de conclure (bruit, taille du
modèle, état du cache d'images).
