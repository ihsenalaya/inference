#!/usr/bin/env python3
"""Génère docs/runbooks/<alerte>.md (symptôme, vérifications, leviers d'optimisation)."""
import pathlib
OUT = pathlib.Path(__file__).resolve().parent.parent / "docs/runbooks"
OUT.mkdir(parents=True, exist_ok=True)
R = {
 "LabQueueTimeHigh": ("Le temps passé en file avant prefill (p95) est élevé.",
   ["Dashboard 00 ligne 2 : requêtes en attente, usage du cache KV."],
   ["Plus de capacité : réplicas, KEDA (seuil du trigger).", "`max-num-seqs` plus grand si le cache KV le permet.", "Routage EPP : charge par pod (dashboard 00 ligne 5)."]),
 "LabRequestsWaiting": ("Des requêtes attendent depuis plus de 5 min : la capacité est insuffisante.",
   ["`lab:requests_waiting`, KEDA (réplicas désirés/prêts), état du GPU."],
   ["Augmenter les réplicas (`lab.sh gpu-scale 2`) ou activer le scénario `baseline-7b-keda`.", "Revoir `max-num-seqs`, `gpu-memory-utilization`.", "Un cold start de 3-4 min retarde le scale-out : pas de scale-to-zero."]),
 "LabSLOBurnFast": ("Le budget d'erreur d'une classe de charge fond vite : 2 % du budget de 30 jours part en 1 h (burn rate > 14,4x, confirmé sur 5 min).",
   ["Dashboard « SLO par classe » : quelle classe, quel SLI (availability, ttft, e2e) ?", "`slo:burn_rate:5m` et `slo:burn_rate:1h` par classe et SLI.",
    "Cause côté serveur ou côté charge ? File vLLM (`lab:requests_waiting`), cache KV, surcharge (débit entrant > plateau).", "Une seule classe touchée : regarder le profil de cette classe (prompts plus longs ? débit plus haut ?)."],
   ["Surcharge : ajouter un réplica (`lab.sh gpu-scale 2`), limiter le débit de la classe (rpm/tpm LiteLLM), activer KEDA.", "Classe RAG : prefill de prompts longs, modèle plus petit ou prompts plus courts.", "Ne pas relever le seuil du SLO pour faire taire l'alerte : décider d'abord si l'objectif est le bon."]),
 "LabSLOBurnSlow": ("Fuite lente du budget d'erreur : 5 % du budget part en 6 h (burn rate > 6x, confirmé sur 30 min).",
   ["Même lecture que LabSLOBurnFast, sur une durée plus longue : la dégradation est modérée mais continue."],
   ["Ouvrir un ticket : tendance (charge qui monte, régression de configuration récente dans Git).", "Comparer avec le dernier run de référence du même profil (docs/BASELINE.md)."]),
 "LabGPUXidError": ("Le GPU a signalé une erreur XID (code d'erreur NVIDIA : matériel, pilote ou application).",
   ["Lire le code : métrique `DCGM_FI_DEV_XID_ERRORS` (dernier code vu) et journal du noyau du nœud (lignes `NVRM: Xid`).", "Table officielle NVIDIA : https://docs.nvidia.com/deploy/xid-errors/ ; résumé : docs/gpu/04-diagnostic-et-optimisation.md.",
    "`nvidia-smi -q` (ECC, pages retirées) depuis le pod `nvidia-driver-daemonset`."],
   ["XID 13, 31, 43, 45 : le plus souvent une faute de l'application : redémarrer le pod vLLM ; si cela se répète sur le même GPU, diagnostic matériel (`dcgmi diag`).",
    "XID 48 (erreur ECC double) : si 63 ou 64 suit, vider le nœud puis réinitialiser. Sur une VM le reset du GPU est souvent impossible : redémarrer ou remplacer le nœud.",
    "XID 79 (GPU tombé du bus PCIe) : vider et remplacer le nœud, contacter le support.", "XID 94 : redémarrer l'application touchée ; XID 95 : réinitialiser le GPU avant de relancer ; XID 119 et 120 (GSP) : redémarrer le nœud."]),
 "LabGPUThrottling": ("Le GPU ralentit ses horloges pour une cause matérielle ou thermique (pas le simple plafond de puissance logiciel, qui est normal).",
   ["Dashboard 07 « Santé du GPU », ligne « Horloges et bridage ».", "`nvidia-smi -q -d PERFORMANCE,TEMPERATURE,POWER` depuis le pod du pilote : quelles raisons sont actives ?",
    "Masque `DCGM_FI_DEV_CLOCK_THROTTLE_REASONS` : 0x8 ralentissement matériel, 0x20 ralentissement thermique logiciel, 0x40 ralentissement thermique matériel, 0x80 frein de puissance matériel."],
   ["Thermique : réduire la charge ; si cela dure, signaler le nœud et le remplacer (sur Azure, le refroidissement n'est pas à notre portée).", "Frein de puissance matériel (0x80) : cause externe à la carte (alimentation) : remplacer le nœud.",
    "Comparer avec l'autre GPU (dashboard 08, ligne « Comparer les GPU ») pour distinguer un nœud défaillant d'une charge trop forte."]),
 "LabGPUThermalMarginLow": ("La température du GPU approche de sa limite de fonctionnement : le bridage thermique approche.",
   ["Dashboard 07 : température, marge thermique, puissance.", "`nvidia-smi -q -d TEMPERATURE` : seuils réels de ce GPU (Max Operating, Slowdown, Shutdown)."],
   ["Réduire la charge continue ou ajouter un réplica pour la répartir.", "Si la marge reste faible à charge modérée, le nœud est suspect : le comparer à l'autre GPU et le remplacer si besoin."]),
 "LabGPUEccUncorrectable": ("Le GPU a détecté une erreur mémoire double, non corrigeable : donnée potentiellement fausse, matériel suspect.",
   ["`DCGM_FI_DEV_ECC_DBE_VOL_TOTAL` et le cumul à vie `DCGM_FI_DEV_ECC_DBE_AGG_TOTAL` ; pages retirées (`nvidia-smi -q -d PAGE_RETIREMENT`).", "Journal du noyau : XID 48, puis 63 ou 64."],
   ["Vider le nœud (cordon + drain), le redémarrer ou le remplacer : une erreur double n'est pas à ignorer.", "Ne pas remettre le nœud en service sans diagnostic (`dcgmi diag -r 2`, vLLM arrêté)."]),
 "LabGPUPageRetirementPending": ("Des pages mémoire du GPU sont marquées pour retrait : elles ne le seront qu'au prochain redémarrage (GPU avant l'A100, comme le T4).",
   ["`nvidia-smi -q -d PAGE_RETIREMENT` : pages retirées (erreurs simples ou doubles) et en attente.", "Journal du noyau : XID 63."],
   ["Planifier un redémarrage du nœud à un moment calme (vider d'abord).", "Si les retraits se répètent ou échouent (XID 64), remplacer le nœud."]),
 "LabGPUPcieReplays": ("Le lien PCIe entre le GPU et la machine a dû rejouer des transferts : lien instable.",
   ["`DCGM_FI_DEV_PCIE_REPLAY_COUNTER` ; débit PCIe (`DCGM_FI_PROF_PCIE_TX_BYTES` / `RX`)."],
   ["Un rejeu isolé est bénin ; une série signale un problème matériel : vider et remplacer le nœud (risque de XID 79)."]),
 "LabGPUMissing": ("Kubernetes annonce un nombre de GPU différent de celui que DCGM voit : un GPU manque, ou le plugin ou l'exporteur est en panne.",
   ["`kubectl get nodes -o custom-columns=...` (champ `nvidia.com/gpu` allouable) ; pods `nvidia-device-plugin-daemonset` et `nvidia-dcgm-exporter` dans `gpu-operator`.", "`nvidia-smi -L` depuis le pod du pilote."],
   ["Redémarrer le DaemonSet fautif ; si `nvidia-smi` ne voit pas le GPU, le nœud est à remplacer."]),
 "LabKVCacheSaturated": ("Le cache KV dépasse le seuil : risque de préemptions et de latence.",
   ["Dashboard 00 : usage du cache KV, préemptions."],
   ["Réduire `max-model-len` ou `max-num-seqs`.", "Augmenter `gpu-memory-utilization` (avec prudence sur 16 Go).", "Modèle quantizé : plus de place pour le KV (le KV en FP8 n'est pas dispo sur Triton)."]),
 "LabPreemptions": ("vLLM évince des requêtes faute de place dans le cache KV.",
   ["`vllm:num_preemptions_total`, usage du cache KV."],
   ["Mêmes leviers que LabKVCacheSaturated.", "Limiter la concurrence côté LiteLLM (rpm/tpm de l'équipe)."]),
 "LabKedaAtMaxWithQueue": ("KEDA est au maximum de réplicas et la file n'est pas vide.",
   ["`kubectl -n inference get scaledobject,hpa`", "Quota T4 : 2 nœuds maximum."],
   ["Relever `maxReplicas` (et `gpu-scale`).", "Alléger le modèle ou quantizer.", "Revoir le seuil du trigger."]),
 "LabGPUTemperatureHigh": ("La température du GPU dépasse le seuil.", ["Dashboard 02 : température, puissance, throttling."],
   ["Réduire la charge continue.", "Un T4 passif dépend du refroidissement du châssis Azure : remplacer le nœud si persistant."]),
 "LabGPUMemoryHigh": ("La mémoire du GPU approche de la limite : risque d'OOM CUDA.", ["Dashboard 02 : mémoire par pod."],
   ["Réduire `gpu-memory-utilization` ou `max-model-len`.", "Scénario gpu-sharing : revoir la répartition des parts."]),
 "LabGPUIdleCost": ("Un nœud GPU allumé est inactif depuis plus de 30 minutes : il coûte sans servir.", ["Dashboard 03 : part d'inactivité, coût horaire."],
   ["`lab.sh stop` (désalloue le cluster) ou `lab.sh gpu-scale 0`.", "Au bout du lab : `lab.sh down`."]),
 "LabGPULowUtilWithQueue": ("Le GPU est peu utilisé alors que des requêtes attendent : le goulot est ailleurs.",
   ["CPU du pod vLLM (tokenisation, scheduling), réseau, `cpu` throttling du conteneur.", "Dashboard 01 : décomposition du temps."],
   ["Augmenter les requests/limits CPU du pod vLLM.", "Vérifier le surcoût LiteLLM / Gateway.", "`max-num-seqs`, `max-num-batched-tokens` trop bas."]),
 "LabVLLMRestarting": ("Un pod vLLM a redémarré.", ["`kubectl -n inference describe pod`, `logs --previous`, événements (Loki)."],
   ["OOM : réduire `gpu-memory-utilization` / mémoire hôte.", "Sonde de démarrage trop courte : `startupFailureThreshold`."]),
 "LabVLLMOOMKilled": ("Un conteneur a été tué par le noyau (mémoire hôte).", ["`kubectl describe pod` : limits mémoire, allocatable du nœud."],
   ["Relever `limits.memory` (28 Gio par nœud T4, ~24 allouables).", "Réduire `max-model-len` / `max-num-seqs`."]),
 "LabScrapeTargetMissing": ("Une cible de scrape (vLLM, DCGM, LiteLLM) est absente.", ["Prometheus > Status > Targets ; ServiceMonitors de `gitops/observability/config`."],
   ["Port du Service workload (`http` depuis KServe 0.21).", "`honorLabels` du ServiceMonitor DCGM.", "Pods NotReady (cold start en cours ?)."]),
 "LabLiteLLMDown": ("Le déploiement LiteLLM n'a pas de réplica disponible.", ["`kubectl -n gateway describe deploy/litellm`, logs, PostgreSQL."],
   ["Secret `litellm-secrets` / base PostgreSQL.", "Mémoire (limit 1,25 Gio)."]),
 "LabLiteLLMBudgetNearlyExhausted": ("Le budget d'une équipe LiteLLM est presque épuisé.", ["Métriques `litellm_remaining_team_budget_metric`."],
   ["Relever `max_budget` via l'API LiteLLM `/team/update`."]),
 "LabArgoAppUnhealthy": ("Une application Argo CD est dégradée ou désynchronisée.", ["`lab.sh status`, UI Argo CD (`lab.sh ui`), `kubectl -n argocd get app <nom> -o yaml`."],
   ["Ordre des vagues, CRD manquantes, ressources refusées (ServerSideApply).", "Self-heal corrige les modifications manuelles."]),
 "LabCorruptedRequests": ("vLLM détecte des NaN dans les logits : sortie corrompue.", ["Modèle concerné ; test de bon sens B5 (T=0 et T=0.7)."],
   ["float16 instable (ex. Gemma 3) : changer de modèle.", "Passer en `--dtype float32` pour diagnostiquer (hors budget mémoire du T4)."]),
 "LabTestAlert": ("Alerte de test (active seulement si `lab_test_alert_enabled == 1`).", ["Vérifier la réception par le récepteur Alertmanager."], ["Aucun."]),
 "EPPHighErrorRatio": ("Plus de 5 % des requêtes traitées par l'EPP échouent.", ["Logs de l'EPP : `kubectl -n inference logs deploy/<modèle>-kserve-router-scheduler`."], ["TLS Gateway -> EPP (DestinationRule).", "Pods vLLM NotReady."]),
 "EPPCriticalErrorRatio": ("Plus de 20 % des requêtes EPP échouent : chemin d'inférence dégradé.", ["Idem EPPHighErrorRatio."], ["Idem ; envisager un rollback du scénario."]),
 "EPPNoReadyEndpoints": ("Le pool n'a aucun endpoint prêt : aucun routage possible.", ["Pods vLLM prêts ? `kubectl -n inference get pods`"], ["Cold start en cours ; patienter ou vérifier le chargement du modèle."]),
 "EPPMetricsAbsent": ("Aucune métrique EPP n'est collectée.", ["ServiceMonitor `lab-epp`, jeton du ServiceAccount Prometheus."], ["Authentification du /metrics de l'EPP (bearerTokenFile)."]),
 "EPPDataLayerPollErrors": ("L'EPP n'arrive pas à interroger une source de données : état périmé.", ["Logs de l'EPP."], ["Réseau EPP -> pods vLLM (port 8000)."]),
 "EPPDataLayerExtractErrors": ("Erreurs d'extraction des métriques des pods par l'EPP.", ["Version de vLLM / noms de métriques attendus par l'EPP."], ["Aligner la version de vLLM avec celle de l'EPP."]),
 "EPPExtProcStreamErrors": ("Les flux ext_proc Envoy <-> EPP se terminent en erreur.", ["Logs istio-proxy de la Gateway (Loki dashboard 05)."], ["`DestinationRule` TLS (insecureSkipVerify) vers le service EPP."]),
}
# Mots du glossaire repérés dans le texte d'un runbook : ils alimentent la boîte « Mots à connaître » (tests/gen_doc_boxes.py).
import re, subprocess, sys
GLOSS_KEYS = ["ttft", "tpot", "cache kv", "préemption", "file d'attente", "cold start", "quantization", "cache de préfixes", "keda", "burn rate",
              "budget d'erreur", "slo", "xid", "throttling", "tensor core", "dcgm", "vram", "taint", "goodput", "saturation", "epp", "tls", "gpu_util", "gitops"]


def keys_for(text):
    low = text.lower()
    found = [k for k in GLOSS_KEYS if re.search(r"(?<![\w-])" + re.escape(k) + r"(?![\w-])", low)]
    return (found or ["alerte"])[:6] if found else ["alerte", "runbook"]


for name, (sym, checks, levers) in R.items():
    body = "\n".join(checks) + "\n" + "\n".join(levers) + "\n" + sym
    (OUT / f"{name}.md").write_text(
        f"# {name}\n\n**Symptôme.** {sym}\n\n<!-- mots: {', '.join(keys_for(body))} -->\n<!-- /mots -->\n\n## Vérifications\n\n" + "\n".join(f"- {c}" for c in checks) +
        "\n\n## Leviers d'optimisation\n\n" + "\n".join(f"- {l}" for l in levers) + "\n")
print(len(R), "runbooks")
subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name("gen_doc_boxes.py"))], check=False)
