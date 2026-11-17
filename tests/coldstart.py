#!/usr/bin/env python3
"""Décompose le démarrage à froid d'un déploiement `lab.sh up` à partir des objets Kubernetes et des logs vLLM.
Étapes : nœud GPU créé -> driver NVIDIA prêt -> pod vLLM planifié -> téléchargement du modèle -> pull de l'image
-> chargement/compilation vLLM -> Ready. Usage : tests/coldstart.py   (KUBECONFIG pointant sur le cluster)"""
import datetime, json, re, subprocess
def kj(*a): return json.loads(subprocess.check_output(["kubectl", *a, "-o", "json"], text=True))
def t(s): return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
fmt = lambda a, b: f"{(b - a).total_seconds():6.0f} s"
nodes = [n for n in kj("get", "nodes")["items"] if n["metadata"]["labels"].get("workload") == "inference"]
node = nodes[0]; n0 = t(node["metadata"]["creationTimestamp"])
drv = [p for p in kj("-n", "gpu-operator", "get", "pods")["items"] if p["metadata"]["name"].startswith("nvidia-driver-daemonset") and p["spec"].get("nodeName") == node["metadata"]["name"]][0]
drv_start = t(drv["status"]["startTime"])
drv_ready = max(t(c["lastTransitionTime"]) for c in drv["status"]["conditions"] if c["type"] == "Ready")
val = [p for p in kj("-n", "gpu-operator", "get", "pods")["items"] if p["metadata"]["name"].startswith("nvidia-cuda-validator")]
gpu_ready = max([t(v["status"]["startTime"]) for v in val] or [drv_ready])
pod = [p for p in kj("-n", "inference", "get", "pods", "-l", "kserve.io/component=workload")["items"]][0]
sched = next(t(c["lastTransitionTime"]) for c in pod["status"]["conditions"] if c["type"] == "PodScheduled")
init_done = next(t(c["lastTransitionTime"]) for c in pod["status"]["conditions"] if c["type"] == "Initialized")
ready = next(t(c["lastTransitionTime"]) for c in pod["status"]["conditions"] if c["type"] == "Ready")
main_started = t(next(s for s in pod["status"]["containerStatuses"] if s["name"] == "main")["state"]["running"]["startedAt"])
log = subprocess.run(["kubectl", "-n", "inference", "logs", pod["metadata"]["name"], "-c", "main"], capture_output=True, text=True).stdout
g = lambda rx: (re.search(rx, log) or [None, None])[1]
print("Étape                                              Durée")
print(f"nœud GPU créé -> driver NVIDIA démarré (attente Argo CD + GPU Operator) {fmt(n0, drv_start)}")
print(f"installation du driver (compilation des modules noyau)               {fmt(drv_start, drv_ready)}")
print(f"nœud GPU créé -> GPU annoncé (nvidia.com/gpu)                        {fmt(n0, gpu_ready)}")
print(f"pod vLLM planifié -> modèle téléchargé (storage-initializer)         {fmt(sched, init_done)}")
print(f"modèle téléchargé -> conteneur vLLM démarré (pull image ~9 Go)       {fmt(init_done, main_started)}")
print(f"conteneur démarré -> Ready (chargement + compilation + graphes CUDA) {fmt(main_started, ready)}")
print(f"nœud GPU créé -> vLLM Ready (total)                                  {fmt(n0, ready)}")
print("\nvLLM :", "poids", g(r"Loading weights took ([\d.]+) seconds"), "s ; modèle", g(r"Model loading took ([\d.]+ GiB)"),
      "; torch.compile", g(r"torch.compile took ([\d.]+) s"), "s ; init moteur", g(r"init engine .* took ([\d.]+) s"), "s ; cache KV", g(r"GPU KV cache size: ([\d,]+) tokens"), "tokens")
print("backend d'attention :", g(r"Using (\w+) attention backend"), "; noyau linéaire :", g(r"Using (\w+) for AutoAWQMarlinLinearMethod") or g(r"Using (\w+LinearKernel)"))
