# 03 - Les dashboards : deux nouveaux tableaux de bord pour lire le GPU

**En une phrase.** Un tableau de bord utile répond à **une question par ligne**, du plus important (en haut) au plus fin (en bas). Deux nouveaux dashboards sont ajoutés :
**07 - Santé du GPU** (« est-il malade ? ») et **08 - Efficacité et goulot du GPU** (« est-il bien utilisé, et par quoi est-il limité ? »).

<!-- mots: dashboard, panneau, méthode use, marge, raisons de bridage, mfu, goodput -->
> **Mots à connaître**
> - **Dashboard / panneau / annotation** : Page Grafana / un graphique / un repère de temps (début et fin d'un bench).
> - **Méthode USE** : Pour chaque ressource, on regarde l'Utilisation (est-elle occupée ?), la Saturation (y a-t-il de la file ?) et les Erreurs.
> - **Marge (headroom)** : Ce qu'il reste avant une limite : degrés avant la limite thermique, watts avant le plafond de puissance.
> - **Raisons de bridage (clock event reasons)** : Les causes qui font baisser l'horloge : repos, plafond de puissance, ralentissement thermique ou matériel... Un masque de bits (`DCGM_FI_DEV_CLOCK_THROTTLE_REASONS`) à décoder.
> - **MFU / MBU** : Part du calcul (MFU) ou de la bande passante mémoire (MBU) réellement utilisée par rapport au maximum du GPU. Le MBU est le bon indicateur du décodage.
> - **Goodput** : Débit des requêtes **réussies et assez rapides** (qui respectent le SLO), pas le débit brut.
> - Tous les mots : [glossaire](../sre/GLOSSAIRE.md).
<!-- /mots -->

**Statut** : générés par `tests/gen_dashboards.py` et chargés par Argo CD comme les autres. Validés **statiquement** (158 requêtes PromQL de syntaxe valide, noms de champs DCGM vérifiés), puis **évalués sur des données réelles le 17/11/2026** (`python3 tests/check_panels.py http://127.0.0.1:19090 240`, fin de la séance GPU) : **les 36 panneaux des dashboards 07 et 08 renvoient des données**, aucun n'est vide.
Sur l'ensemble des dashboards, 101 panneaux ont des données et 9 sont vides : tous du dashboard **06 (SLO par classe)**, parce que les mesures de la séance GPU ont été faites directement sur vLLM (`--target direct`) et que ces SLI se lisent dans les métriques de LiteLLM. C'est attendu, pas un défaut.
**Limite** : on a vérifié que les requêtes renvoient des valeurs, pas que les graphiques sont lisibles à l'écran dans Grafana (non regardé).

## 1. Les dashboards du lab, et où se situent les nouveaux

| Dashboard | Question | Nouveau ? |
|---|---|---|
| 00 - Cockpit d'optimisation | les utilisateurs sont-ils bien servis ? | existe |
| 01 - Anatomie d'une requête | où va le temps d'une requête ? | existe |
| 02 - GPU en profondeur | quelles sont les mesures brutes du GPU, du CPU, de l'allocation ? | existe |
| 03 - Capacité et coût | combien ça coûte, combien ça tient ? | existe |
| 04 - Comparaison de runs, 05 - Logs, 06 - SLO par classe | avant / après ; erreurs ; objectifs | existent |
| **07 - Santé du GPU** | **est-il en bonne santé ?** | **nouveau** (18 panneaux) |
| **08 - Efficacité et goulot du GPU** | **est-il saturé, efficace, par quoi est-il limité ?** | **nouveau** (18 panneaux) |

Le 02 reste le dashboard « loupe » (valeurs brutes) ; le 07 et le 08 sont des **dashboards de décision** : chacun a un état « tout va bien » facile à reconnaître.

## 2. Dashboard 07 - Santé du GPU

```text
┌───────────────────────────── 07 - Santé du GPU ─────────────────────────────┐
│ SANTÉ EN UN COUP D'ŒIL (tout doit être vert)                                │
│ [GPU vus][GPU annoncés][Dernier XID][ECC doubles][Bridage matériel][Marge °C]│
├─────────────────────────────────────────────────────────────────────────────┤
│ THERMIQUE ET PUISSANCE                                                      │
│ [Température et limite]   [Puissance et limite]   [Marges (W et °C)]        │
├─────────────────────────────────────────────────────────────────────────────┤
│ HORLOGES ET BRIDAGE                                                         │
│ [Horloges SM et mémoire] [Horloge / max] [Bridage décodé 0/1] [Durées]      │
├─────────────────────────────────────────────────────────────────────────────┤
│ ERREURS MÉMOIRE, XID ET PCIe (doivent rester à zéro)                        │
│ [ECC SBE / DBE]          [Pages retirées]        [XID et rejeux PCIe]       │
├─────────────────────────────────────────────────────────────────────────────┤
│ SERVICES GPU DANS KUBERNETES                                                │
│ [DaemonSets GPU Operator : prêts / souhaités]    [Cible DCGM : up]          │
└─────────────────────────────────────────────────────────────────────────────┘
```

| Ligne | Panneau | Ce qu'il répond | Comment le lire |
|---|---|---|---|
| Coup d'œil | GPU vus par DCGM / annoncés par Kubernetes | « tous mes GPU sont-ils là ? » | les deux nombres doivent être égaux ; un écart déclenche `LabGPUMissing` |
| Coup d'œil | Dernier code XID | « le GPU a-t-il signalé une erreur ? » | 0 = vert ; tout autre code : voir la table XID ([04](04-diagnostic-et-optimisation.md)) |
| Coup d'œil | Erreurs ECC doubles | « la mémoire est-elle fiable ? » | 0 = vert ; ≥ 1 = rouge, nœud à vider |
| Coup d'œil | Bridage matériel / thermique | « le GPU ralentit-il pour une mauvaise raison ? » | 0 = vert ; 1 = rouge. Le plafond de puissance **logiciel** n'est pas compté |
| Coup d'œil | Marge thermique | « suis-je loin de la limite ? » | vert ≥ 8 °C, orange 3 à 8, rouge < 3 |
| Thermique | Température et limite | « comment chauffe-t-il ? » | la courbe doit rester sous la limite ; un T4 est refroidi passivement |
| Thermique | Puissance et limite | « suis-je au plafond ? » | près de 70 W = le GPU baisse ses horloges pour rester dans l'enveloppe |
| Thermique | Marges (W et °C) | « combien me reste-t-il ? » | deux unités : lire chaque courbe avec sa légende |
| Horloges | Horloges SM et mémoire | « à quelle vitesse tourne-t-il ? » | 585 MHz au repos (observé) ; monte en charge |
| Horloges | Horloge SM rapportée au maximum | « suis-je loin du maximum ? » | 1 = maximum ; charge forte avec un rapport bas et une puissance proche de 70 W = limité par la puissance |
| Horloges | **Bridage décodé** | « pourquoi ralentit-il ? » | deux courbes 0/1 : plafond logiciel (**normal**) et ralentissement matériel/thermique (**anormal**) |
| Horloges | Temps de bridage (compteurs de durée) | « combien de temps bridé ? » | lire la forme, pas la valeur (unité à confirmer) |
| Erreurs | ECC, pages retirées, XID et rejeux PCIe | « quelque chose s'abîme-t-il ? » | tout doit rester à zéro ; une marche d'escalier est un événement à dater |
| Services | DaemonSets GPU Operator, cible DCGM | « la plomberie GPU tourne-t-elle ? » | prêts = souhaités ; cible = 1 |

**Lecture en 30 secondes** : la première ligne est verte ? Alors la santé est bonne ; sinon descendez à la ligne qui correspond à la case rouge.

## 3. Dashboard 08 - Efficacité et goulot du GPU

```text
┌──────────────────────── 08 - Efficacité et goulot du GPU ───────────────────────┐
│ UTILISATION : quelles ressources travaillent ?                                  │
│ [Calcul : SM, tensor, moteur]  [Mémoire : DRAM ÷ 0,8]  [VRAM utilisée]          │
├─────────────────────────────────────────────────────────────────────────────────┤
│ SATURATION : y a-t-il de la file ?                                              │
│ [File et batch]               [Cache KV et préemptions] [Part de prefill]       │
├─────────────────────────────────────────────────────────────────────────────────┤
│ MFU ET MBU (scénario gpu-health)                                                │
│ [MFU]                         [MBU]                    [MBU vs DRAM_ACTIVE]     │
├─────────────────────────────────────────────────────────────────────────────────┤
│ ÉNERGIE ET COÛT                                                                 │
│ [Tokens/s][Puissance][Tokens/joule · kWh/M][Joules/requête]                     │
│ [$ par M tokens · coût d'inactivité]        [GPU alloués, utilisés, inactifs]   │
├─────────────────────────────────────────────────────────────────────────────────┤
│ COMPARER LES GPU ENTRE EUX                                                      │
│ [Température et puissance par GPU]  [Écart de température]  [J par token/pod]  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

| Ligne | Panneau | Ce qu'il répond | Comment le lire |
|---|---|---|---|
| Utilisation | Calcul : unités actives et tensor cores | « le calcul est-il exploité ? » | `SM_ACTIVE` ≥ 0,8 nécessaire mais pas suffisant ; `TENSOR` plus haut avec l'AWQ (observé) |
| Utilisation | Mémoire : DRAM ÷ maximum pratique | « la bande passante est-elle le goulot ? » | proche de 1 = bande passante au maximum (décodage) |
| Utilisation | VRAM utilisée | « la mémoire est-elle pleine ? » | vLLM préalloue : une VRAM pleine ne signifie rien |
| Saturation | File et batch | « la capacité est-elle dépassée ? » | `en attente` > 0 durablement = oui ; `en cours` = taille du batch |
| Saturation | Cache KV et préemptions | « manque-t-il de la mémoire de contexte ? » | KV proche de 100 % puis préemptions = saturation mémoire |
| Saturation | Part du temps en prefill | « charge de type RAG ou chat ? » | haut = calcul (RAG), bas = mémoire (chat) |
| MFU / MBU | MFU, MBU, MBU contre DRAM_ACTIVE | « quelle part du maximum utilise-t-on ? » | le MBU est le bon indicateur du décodage ; les deux mesures de mémoire doivent évoluer ensemble |
| Énergie | Tokens/s, puissance, tokens/joule, kWh par million, joules par requête | « combien d'énergie par token ? » | plus on charge, moins chaque token coûte (1,5B : × 3,7) |
| Énergie | Dollars par million de tokens, coût d'inactivité, GPU alloués/utilisés/inactifs | « paie-t-on pour rien ? » | un GPU alloué et inactif coûte 0,526 $/h pour rien |
| Comparer | Température et puissance par GPU, écart, joules par token et par pod | « un GPU est-il différent de l'autre ? » | deux GPU sous la même charge doivent se ressembler |

**Lecture en 60 secondes** : (1) la ligne Saturation : y a-t-il de la file ? (2) si oui, la ligne Utilisation : calcul ou mémoire ? (3) la ligne Énergie : à quel coût ?
Ensuite, l'arbre de décision de [04](04-diagnostic-et-optimisation.md) donne le levier.

## 4. Trois scénarios de lecture

1. **« Les utilisateurs se plaignent de lenteur. »** → 08, ligne Saturation : file > 0 ? Oui → ligne Utilisation : `SM_ACTIVE` haut et `DRAM ÷ 0,8` bas = limité par le calcul (modèle plus petit, réplica) ; `DRAM ÷ 0,8` haut = limité par la mémoire (quantization, moins de contexte).
2. **« Une alerte de santé vient de sonner. »** → 07, ligne « Coup d'œil » : quelle case est rouge ? Descendre à la ligne correspondante, relever l'heure du changement, ouvrir le runbook de l'alerte.
3. **« Le GPU coûte cher et sert peu. »** → 08, ligne Énergie : GPU alloués et inactifs ? tokens par joule bas ? → arrêter, réduire ou charger davantage (voir 04).

## 5. Comment ces dashboards sont fabriqués (traçabilité)

- Source : `tests/gen_dashboards.py` (sections 07 et 08) → JSON dans `gitops/observability/config/dashboards/Lab/` → ConfigMaps chargées par le sidecar de Grafana.
- Les règles `lab:gpu_*` sont dans `gitops/observability/config/templates/rules.yaml` (groupe `lab.gpu_health`) ; les limites matérielles (70 W, 85 °C, 1 590 MHz, 320 Go/s, 65 TFLOPS, 0,8) sont des **réglages** (`gpuLimits`, `values.yaml`), à confirmer avec `nvidia-smi -q`.
- Contrôles : `tests/check_dashboard_promql.py` (syntaxe), `tests/check_dcgm_fields.py` (noms de champs), `tests/promtool/lab_rules_test.yml` (18 tests dont les règles de santé) ; sur un cluster : `tests/check_panels.py`.

## 6. Exercice (à faire vous-même)

Objectif : prédire ce que vous verrez **avant** de lancer la charge.
1. Vous lancez le profil `decode-only` (prompts courts, longues réponses). Quelle courbe du dashboard 08 monte en premier : `SM_ACTIVE`, `DRAM ÷ 0,8` ou la part de prefill ? Pourquoi ?
2. Vous lancez ensuite `prefill-only`. Que devient `DRAM ÷ 0,8` ?
Vérification : en decode pur la mémoire domine (`DRAM ÷ 0,8` haut, part de prefill basse) ; en prefill pur `DRAM ÷ 0,8` chute et la part de prefill approche 100 %.
