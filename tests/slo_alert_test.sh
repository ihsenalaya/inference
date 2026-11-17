#!/usr/bin/env bash
# Essai réel d'une alerte de burn rate : surcharge volontaire de la classe RAG (prompts longs au-dessus de la capacité), puis
# surveillance de LabSLOBurnFast dans Prometheus/Alertmanager et du récepteur d'alertes. Usage : tests/slo_alert_test.sh [débit] [durée s]
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
RATE="${1:-0.5}"; DUR="${2:-600}"; LOG="${TMPDIR:-/tmp}/slo-alert-test.log"
(BENCH_KEY=lab-rag PER_REQUEST=true RESULT_TAG=overload RAG_RATE="$RATE" DURATION="$DUR" WARMUP=0 BENCH_TIMEOUT=1800 ./lab.sh bench long-prompt >"$LOG" 2>&1 &)
t0=$(date +%s)
echo "== surcharge RAG à $RATE req/s pendant $DUR s ($(date +%T))"
q() { curl -s --data-urlencode "query=$1" http://127.0.0.1:19090/api/v1/query | python3 -c "import sys,json; r=json.load(sys.stdin)['data']['result']; print(' '.join(f\"{x['metric'].get('sli','')}={float(x['value'][1]):.3g}\" for x in r) or '-')"; }
fired=""
while [[ $(( $(date +%s) - t0 )) -lt $(( DUR + 300 )) ]]; do
  b1="$(q 'slo:burn_rate:1h{class="rag"}')"; b5="$(q 'slo:burn_rate:5m{class="rag"}')"
  a="$(curl -s http://127.0.0.1:19090/api/v1/alerts | python3 -c "import sys,json; print(','.join(sorted({x['labels']['alertname']+':'+x['labels'].get('sli','')+':'+x['state'] for x in json.load(sys.stdin)['data']['alerts'] if x['labels']['alertname'].startswith('LabSLO')})) or '-')")"
  echo "$(date +%T) t+$(( $(date +%s) - t0 ))s burn1h[$b1] burn5m[$b5] alertes[$a]"
  [[ -z "$fired" && "$a" == *LabSLOBurnFast*firing* ]] && { fired=$(( $(date +%s) - t0 )); echo ">>> LabSLOBurnFast FIRING à t+${fired}s"; }
  sleep 30
done
echo "premier déclenchement : ${fired:-jamais} s"
