#!/usr/bin/env bash
# Critère 9 sur un vrai modèle : `bench burst` doit faire passer le modèle de 1 à 2 réplicas, puis revenir à 1.
# Mesure trois délais : décision (HPA desired=2), pod Ready, premier token servi par le nouveau réplica (vllm:request_success_total > 0).
# Prérequis : scénario baseline-7b-keda actif, 2 nœuds GPU. Usage : tests/keda_timeline.sh
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
NS=inference
DEPLOY="${DEPLOY:-qwen-7b-awq-kserve}"
t0=$(date +%s)
log() { echo "[+$(( $(date +%s) - t0 ))s] $*"; }
kubectl -n monitoring port-forward svc/kps-prometheus 19091:9090 >/dev/null 2>&1 &
PF=$!
trap 'kill $PF 2>/dev/null' EXIT
sleep 3
RATE="${RATE:-3}" DURATION="${DURATION:-240}" ./lab.sh bench burst >/tmp/keda-burst.log 2>&1 &
BP=$!
log "pic de charge lancé (profil burst)"
decided=""; ready=""; served=""
while kill -0 $BP 2>/dev/null || [ -z "$served" ]; do
  d=$(kubectl -n $NS get hpa -o jsonpath='{.items[0].status.desiredReplicas}' 2>/dev/null)
  r=$(kubectl -n $NS get deploy "$DEPLOY" -o jsonpath='{.status.readyReplicas}' 2>/dev/null)
  [ -z "$decided" ] && [ "${d:-1}" -ge 2 ] && { decided=1; log "décision de scale-out : desired=2"; }
  [ -z "$ready" ] && [ "${r:-0}" -ge 2 ] && { ready=1; log "2e pod Ready"; }
  if [ -n "$ready" ] && [ -z "$served" ]; then
    n=$(curl -s -m 10 -G http://127.0.0.1:19091/api/v1/query --data-urlencode 'query=count(vllm:request_success_total{namespace="inference"} > 0)' | python3 -c "import sys,json;r=json.load(sys.stdin)['data']['result'];print(int(float(r[0]['value'][1])) if r else 0)" 2>/dev/null)
    [ "${n:-0}" -ge 2 ] && { served=1; log "premier token servi par le nouveau réplica"; }
  fi
  kill -0 $BP 2>/dev/null || [ -n "$served" ] || [ $(( $(date +%s) - t0 )) -gt 1500 ] && break
  sleep 5
done
wait $BP 2>/dev/null
log "fin du pic ; attente du retour à 1 réplica (cooldown KEDA 300 s)"
for _ in $(seq 1 90); do
  r=$(kubectl -n $NS get deploy "$DEPLOY" -o jsonpath='{.status.replicas}' 2>/dev/null)
  [ "${r:-2}" -le 1 ] && { log "retour à 1 réplica"; exit 0; }
  sleep 10
done
log "pas de retour à 1 réplica dans le délai"; exit 1
