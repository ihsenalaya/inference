# 06 - Correspondance avec le référentiel NCP-AIO : ce que ce travail démontre

**En une phrase.** Un référentiel d'examen liste des compétences ; ce chapitre dit, pour chacune de celles qui touchent au GPU en exploitation, **quelle preuve concrète** existe dans ce dépôt, et **ce qui n'est pas couvert**.
Le but est de montrer des compétences dans un **environnement réel d'inférence**, pas de recopier un programme.

<!-- mots: dcgm, nvidia-smi, xid, ecc, mfu, méthode use, gitops -->
> **Mots à connaître**
> - **DCGM** : Outil NVIDIA qui mesure le GPU ; `dcgm-exporter` publie ces mesures pour Prometheus.
> - **nvidia-smi** : Commande NVIDIA qui affiche l'état du GPU : température, puissance, horloges, mémoire, erreurs.
> - **XID** : Code d'erreur NVIDIA signalant un problème GPU (ex. 79 : GPU tombé du bus).
> - **ECC / SBE / DBE** : Code qui détecte et corrige les erreurs de la mémoire du GPU. SBE = erreur simple, corrigée ; DBE = erreur double, non corrigeable (grave).
> - **MFU / MBU** : Part du calcul (MFU) ou de la bande passante mémoire (MBU) réellement utilisée par rapport au maximum du GPU. Le MBU est le bon indicateur du décodage.
> - **Méthode USE** : Pour chaque ressource, on regarde l'Utilisation (est-elle occupée ?), la Saturation (y a-t-il de la file ?) et les Erreurs.
> - **GitOps** : L'état voulu du cluster est écrit dans Git ; Argo CD le fait appliquer. On ne modifie pas le cluster à la main.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

Référentiel utilisé : la page publique « NVIDIA-Certified Professional: AI Operations (NCP-AIO) » de NVIDIA (lue le 17/11/2026 ; vérifier les détails sur la page, qui peut évoluer). Ce document **ne dit rien** sur la situation personnelle de l'auteur du dépôt : il relie des compétences à des preuves.

Statuts : **démontré** (réalisé et mesuré sur le cluster réel) · **construit** (écrit, validé par tests statiques, pas encore exécuté) · **hors périmètre** (le lab ne peut pas le démontrer).

## 1. Les domaines du référentiel (page publique)

| Domaine | Poids | Contenu cité par la page |
|---|---|---|
| Install and Deploy | 31 % | BCM, Kubernetes sur hôtes NVIDIA via BCM, conteneurs NGC et images cloud, stockage de datacenter IA, services DOCA sur DPU |
| Administration | 23 % | Fleet Command, Slurm, architecture de datacenter IA, Run:ai, **configuration de MIG** |
| Workload Management | 23 % | **administration de clusters Kubernetes**, **DCGM, NVSM, nvidia-smi pour dépanner**, administration de BCM et provisionnement |
| Troubleshooting and Optimization | 23 % | Docker, Fabric Manager (NVLink/NVSwitch), BCM, Magnum IO, performance du stockage |
| Responsabilités clés | - | « surveiller la santé du cluster et l'utilisation des ressources » ; « maintenir les plateformes de calcul GPU, pilotes, logiciels et conteneurs » |

## 2. Compétence par compétence

| Compétence du référentiel | Preuve dans ce dépôt | Statut |
|---|---|---|
| **Surveiller la santé et l'utilisation des ressources** | dashboards **07 (santé)** et **08 (efficacité)**, 14 KPI, méthode USE ([README](README.md), [02](02-kpi.md), [03](03-dashboards.md)) ; dashboards antérieurs (cockpit, GPU, capacité, SLO...) | **démontré** : les 14 règles KPI évaluent sans erreur sur le cluster (359 règles saines) et leurs valeurs ont été lues pendant la séance GPU du 17/11 ([07](07-resultats-seance.md)) ; dashboards 07 et 08 : **construits** (validés par 158 requêtes, non regardés dans Grafana) ; dashboards antérieurs : 72 panneaux sur 74 avec données le 17/11 |
| **Utiliser DCGM et nvidia-smi pour dépanner** | catalogue des signaux et décodage du masque de bridage ([01](01-signaux-du-gpu.md)), table XID officielle et arbre de santé ([04](04-diagnostic-et-optimisation.md)), `dcgmi health` et `diag` (S8), instantané `nvidia-smi` | **démontré** : compteurs DCGM lus sur le cluster ; `nvidia-smi -q` par section, `dmon` à 1 Hz, `nvidia-smi -pl` et `-lgc` ; `dcgmi discovery`, `health`, `diag -r 1/2/3`, `dmon`, injection d'erreur ([07](07-resultats-seance.md)) |
| **Lire un GPU : utilisation contre saturation** | « 100 % utilisé ≠ saturé » mesuré (284 contre 933 tokens/s sur le même T4) ; huit situations ; roofline ; MBU ≈ 83 % mesuré (≈ 69 % avec le temps par token du decode pur) | **démontré** ([01](01-signaux-du-gpu.md), [module 5](../formation/05-lire-un-gpu.md)) ; précisé par le decode pur contre le prefill pur et l'escalier de charge ([07 §4-5](07-resultats-seance.md#4-decode-pur-contre-prefill-pur)) |
| **Administrer un cluster Kubernetes** | AKS + GPU Operator, taints et tolérations, DaemonSets GPU, plugin de GPU, autoscaling KEDA, GitOps Argo CD avec self-heal, 21 applications | **démontré** (cluster réel, [guides](../guide/README.md), [fiches de services](../services/00-index.md)) |
| **Maintenir plateformes GPU, pilotes, conteneurs** | échec de compilation du pilote ouvert sur le noyau AKS, passage aux modules propriétaires (driver 580.95.05, CUDA 13.0) ; démarrage d'un nœud GPU ramené de 1 228 s à 721 s (GPU Operator en vague 1, pré-tirage de l'image) | **démontré** ([DECISIONS](../DECISIONS.md) D-18 et D-27, [module 6](../formation/06-demarrage-a-froid.md)) ; **montée de version de pilote : non faite** |
| **Dépanner et optimiser** | méthode de mesure (boucle ouverte, bruit, répétitions), goulots, leviers chiffrés, énergie par token ([formation](../formation/README.md), [04](04-diagnostic-et-optimisation.md)) | **démontré** en grande partie |
| **Santé GPU automatisée (équivalent des contrôles d'AKS)** | 6 alertes de santé, 18 tests promtool, injection de XID pour tester le chemin d'alerte (S9) | **démontré** pour le chemin règle -> Prometheus -> Alertmanager -> récepteur (`LabGPUIdleCost` reçue en `firing` puis `resolved`, XID : voir [07 §9](07-resultats-seance.md#9-injection-dun-xid)) ; aucune alerte de santé ne s'est déclenchée sur le GPU sain |
| **Configurer MIG** | - | **hors périmètre** : le T4 n'a pas de MIG |
| **BCM, Slurm, Run:ai, Fleet Command, DOCA/DPU** | - | **hors périmètre** |
| **Fabric Manager, NVLink/NVSwitch, Magnum IO, stockage** | - | **hors périmètre** (un T4 par VM, pas de réseau InfiniBand) |
| **Conteneurs NGC** | les images NVIDIA du GPU Operator viennent de `nvcr.io`, tirées sans authentification | faible : on les utilise, on ne les administre pas |

**Lecture honnête** : ce lab couvre bien la tranche « Kubernetes + GPU en exploitation + observabilité + dépannage », qui correspond surtout au domaine *Workload Management* (23 %) et aux responsabilités clés.
Il ne couvre pas la tranche *BCM / Slurm / Run:ai / MIG / NVLink*, qui pèse la majorité du référentiel. La page officielle ne mentionne pas le GPU Operator : ce lab travaille des compétences **voisines**, utiles en pratique, mais pas la lettre de l'examen.

## 3. Comment le raconter : quatre histoires vraies

Chacune a une situation, une action, un résultat chiffré, et une leçon.

1. **« 100 % utilisé » n'était pas « saturé ».**
   *Situation* : un T4 affiche `GPU_UTIL` 100 % à 2 req/s sur le 1,5B. *Action* : lecture de `SM_ACTIVE`, de `DRAM_ACTIVE` et de la file, puis charge saturée. *Résultat* : le même GPU produit **933 tokens/s au lieu de 284**, avec un `GPU_UTIL` plus bas (83 %).
   *Leçon* : juger la saturation par la file et la méthode USE, pas par un compteur de temps d'occupation.
2. **AKS ne surveille pas la santé de mes GPU : je l'ai reconstruite.**
   *Situation* : notre pool utilise `--gpu-driver none` (pilote du GPU Operator) ; la doc Microsoft précise que la surveillance de santé GPU d'AKS ne s'y applique pas. *Action* : reproduction de ses contrôles (GPU manquant, XID, bridage, ECC) en règles Prometheus, avec 18 tests, et décodage du masque de bits de bridage depuis l'en-tête NVML.
   *Résultat* : 6 alertes de santé et 2 dashboards, **testés ensuite sur le cluster** : le chemin d'alerte a été prouvé de bout en bout (inactivité, XID injecté). *Leçon* : connaître les limites des outils gérés et savoir les compenser.
3. **Le décodage est limité par la mémoire : je l'ai mesuré.**
   *Situation* : pourquoi un 7B quantizé produit-il un token en 21,5 ms ? *Action* : calcul de l'intensité arithmétique (≈ 2,7 opérations par octet) et du toit mémoire de 320 Go/s. *Résultat* : **≈ 83 % du toit**, et un lot saturé qui bascule côté calcul (`DRAM_ACTIVE` 0,27, `SM_ACTIVE` 0,97).
   *Leçon* : un modèle simple (roofline) explique les mesures et guide les leviers.

4. **La limite de puissance, un levier d'efficacité mesuré.**
   *Situation* : un T4 travaille au plafond de 70 W et son horloge reste vers 1 100 MHz au lieu de 1 590. *Action* : `nvidia-smi -pl 60` puis verrouillage d'horloge à 900 et 750 MHz, mêmes charges, mesures DCGM et énergie. *Résultat* : **+ 10 % de tokens par joule pour − 6,5 % de débit** à 60 W, **+ 21 % pour − 8 %** à 900 MHz, gain disparu à 750 MHz (le « genou » de la littérature), au prix d'une latence multipliée par 3 au bord de la capacité.
   *Leçon* : un réglage d'énergie est un choix de **capacité**, pas un gain gratuit ; il se décide avec le goodput et la file, pas seulement avec les watts ([07 §6](07-resultats-seance.md#6-limite-de-puissance-et-verrouillage-dhorloge)).

## 4. Ce que ce travail ne prouve pas

- Aucune expérience sur **BCM, Slurm, Run:ai, MIG, NVLink, DGX** ou un réseau InfiniBand.
- Pas de remplacement de nœud, de montée de pilote ni de partage de GPU (non retenus).
- Les **dashboards 07 et 08** n'ont pas été regardés dans Grafana (les règles et les requêtes l'ont été) ; les alertes de santé sur un **vrai** défaut matériel ne peuvent pas être démontrées (une panne réelle n'est pas reproductible : on injecte une valeur).
- Un lab à un ou deux T4, pas une production.

## 5. Exercice (à faire vous-même)

Objectif : présenter **l'histoire 1** en 90 secondes sans notes. Structure : situation (1 phrase), action (2 phrases), résultat chiffré (1 phrase), leçon (1 phrase).
Vérification : vous citez 284 et 933 tokens/s, `GPU_UTIL` 100 % et 83 %, et vous dites quelles deux autres grandeurs vous avez lues pour juger la saturation.
