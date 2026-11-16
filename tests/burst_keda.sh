#!/usr/bin/env bash
# Test KEDA : un pic de charge doit faire passer le modèle de 1 à 2 réplicas, puis revenir à 1.
# Mesure trois délais : décision (HPA desired=2), pod Ready, retour à 1. Usage : tests/burst_keda.sh [url] [deploy]
set -uo pipefail
URL="${1:-http://127.0.0.1:18080/inference/qwen-1-5b-keda/v1/chat/completions}"
DEPLOY="${2:-qwen-1-5b-keda-kserve}"
MODEL="${MODEL:-Qwen/Qwen2.5-1.5B-Instruct-keda}"
NS=inference
DUR="${DUR:-120}"
t0=$(date +%s)
log() { echo "[+$(( $(date +%s) - t0 ))s] $*"; }
load() { # 40 requêtes concurrentes en boucle pendant $DUR secondes
  end=$(( $(date +%s) + DUR ))
  for _ in $(seq 1 40); do
    ( while [ "$(date +%s)" -lt "$end" ]; do curl -s -m 30 -o /dev/null "$URL" -H 'Content-Type: application/json' \
        -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"charge\"}],\"max_tokens\":16}"; done ) &
  done
  wait
}
log "départ du pic de charge (${DUR}s)"
load >/dev/null 2>&1 &
LP=$!
decided=""; ready=""
while kill -0 $LP 2>/dev/null; do
  d=$(kubectl -n $NS get hpa -o jsonpath='{.items[0].status.desiredReplicas}' 2>/dev/null)
  r=$(kubectl -n $NS get deploy "$DEPLOY" -o jsonpath='{.status.readyReplicas}' 2>/dev/null)
  [ -z "$decided" ] && [ "${d:-1}" -ge 2 ] && { decided=1; log "décision de scale-out : desired=2"; }
  [ -z "$ready" ] && [ "${r:-0}" -ge 2 ] && { ready=1; log "2e pod Ready"; }
  sleep 5
done
log "fin du pic ; attente du retour à 1 réplica (cooldown KEDA)"
for _ in $(seq 1 90); do
  r=$(kubectl -n $NS get deploy "$DEPLOY" -o jsonpath='{.status.replicas}' 2>/dev/null)
  [ "${r:-2}" -le 1 ] && { log "retour à 1 réplica"; exit 0; }
  sleep 10
done
log "pas de retour à 1 réplica dans le délai"; exit 1
