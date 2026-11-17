#!/usr/bin/env bash
# Répète N fois le profil steady (boucle ouverte, échauffement exclu) pour mesurer le bruit. Usage : tests/repeat_steady.sh <débit req/s> [N] [tag]
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
RATE="${1:?débit}"; N="${2:-3}"; TAG="${3:-noise}"
for i in $(seq 1 "$N"); do
  echo "== répétition $i/$N ($(date +%T))"
  RESULT_TAG="${TAG}-r$i" RATE="$RATE" WARMUP=60 DURATION=300 BENCH_TIMEOUT=900 ./lab.sh bench steady
done
