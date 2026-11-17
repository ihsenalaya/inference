#!/usr/bin/env bash
# Protocole de mesure d'un scénario : steady, shared-prefix, long-prompt, puis surcoût de la Gateway (cible gateway).
# Usage : tests/run_baseline.sh [débit steady en req/s]   (le débit se lit sur le sweep : un peu sous la saturation)
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
RATE="${1:-1}"
export BENCH_TIMEOUT="${BENCH_TIMEOUT:-1500}"
echo "== steady (${RATE} req/s)";        RATE="$RATE" DURATION="${STEADY_DURATION:-600}" ./lab.sh bench steady
echo "== shared-prefix (${RATE} req/s, 5 min)";  RATE="$RATE" DURATION=300 ./lab.sh bench shared-prefix
echo "== long-prompt (0,5 req/s, 5 min)";        DURATION=300 ./lab.sh bench long-prompt
echo "== steady direct Gateway (surcoût LiteLLM, 3 min)"; RATE="$RATE" DURATION=180 ./lab.sh bench steady --target gateway
