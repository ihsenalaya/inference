#!/usr/bin/env bash
# Instantané de l'état des GPU depuis le conteneur du pilote NVIDIA : nvidia-smi complet (seuils, limites, horloges, ECC, pages retirées, PCIe)
# + enregistrement à 1 Hz (nvidia-smi dmon) pendant DUREE secondes si DUREE > 0. Usage : tests/gpu_snapshot.sh <étiquette> [durée en s]
# Sortie : results/gpu-<date>-<étiquette>/<pod>-*.txt|csv. Non testé sur cluster (voir docs/gpu/05-simulations.md).
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
LABEL="${1:?étiquette (ex. repos, escalier, soutenu)}"; DUR="${2:-0}"
OUT="results/gpu-$(date +%Y-%m-%d)-${LABEL}"; mkdir -p "$OUT"
pods="$(kubectl -n gpu-operator get pods -l app=nvidia-driver-daemonset -o name 2>/dev/null || true)"
[[ -n "$pods" ]] || { echo "aucun pod nvidia-driver-daemonset : le cluster tourne-t-il (KUBECONFIG) ?" >&2; exit 1; }
for pod in $pods; do
  n="${pod#pod/}"
  kubectl -n gpu-operator exec "$n" -- nvidia-smi -q >"$OUT/$n-nvidia-smi-q.txt"
  kubectl -n gpu-operator exec "$n" -- nvidia-smi \
    --query-gpu=timestamp,index,name,temperature.gpu,power.draw,power.limit,clocks.sm,clocks.mem,utilization.gpu,utilization.memory,memory.used,memory.total \
    --format=csv >"$OUT/$n-instantane.csv"
  if [[ "$DUR" -gt 0 ]]; then
    # groupes : p puissance/température, u utilisation, c horloges, v violations (bridage), m mémoire, e ECC et rejeux PCIe, t débit PCIe
    kubectl -n gpu-operator exec "$n" -- nvidia-smi dmon -s pucvmet -d 1 -c "$DUR" -o T >"$OUT/$n-dmon.txt" &
  fi
done
wait
echo "instantané écrit dans $OUT"
