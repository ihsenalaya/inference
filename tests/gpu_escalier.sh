#!/usr/bin/env bash
# Escalier de charge (S2 de docs/gpu/05-simulations.md) : un run par débit, puis les signaux GPU de la fenêtre de chaque run (tests/run_window.py).
# Usage : RATES="0.5 1 1.5 2 2.5" [PROFILE=steady] tests/gpu_escalier.sh [étiquette]    (Prometheus : port-forward sur 127.0.0.1:19090)
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
export PATH="$HOME/.local/bin:$PATH"
PROFILE="${PROFILE:-steady}"; TAG="${1:-escalier}"; TARGET="${TARGET:-litellm}"
SUF=""; [[ "$TARGET" == litellm ]] || SUF="-$TARGET"
SCEN="$(sed -n 's/^scenario: *//p' gitops/active-azure.yaml)"
for r in ${RATES:-0.5 1 1.5 2 2.5}; do
  echo "== palier $r req/s ($(date +%T))"
  RESULT_TAG="${TAG}-r${r}" RATE="$r" RAG_RATE="$r" WARMUP="${WARMUP:-30}" DURATION="${DURATION:-150}" PER_REQUEST=true BENCH_TIMEOUT=900 ./lab.sh bench "$PROFILE" --target "$TARGET" | tail -6
  d="results/$(date +%Y-%m-%d)-${SCEN}-${PROFILE}${SUF}-${TAG}-r${r}"
  python3 tests/run_window.py "$d" | tail -1
done
