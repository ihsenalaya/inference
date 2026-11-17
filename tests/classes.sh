#!/usr/bin/env bash
# Séance 2 : un run par classe de charge SLO, avec la clé virtuelle LiteLLM de la classe (les métriques serveur par classe) et le
# mode par requête (goodput côté client). Débits par variables : INT_RATE, RAG_RATE, MT_RATE, BATCH_RATE ; DURATION, WARMUP.
# Usage : tests/classes.sh [classes...]   (défaut : interactive rag multiturn batch). Sortie : results/<date>-<scénario>-<profil>-class.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
: "${INT_RATE:=1}" "${RAG_RATE:=0.5}" "${MT_RATE:=1}" "${BATCH_RATE:=3}" "${DURATION:=300}" "${WARMUP:=60}"
SCEN="$(sed -n 's/^scenario: *//p' gitops/active-azure.yaml)"
classes=("$@"); [[ ${#classes[@]} -gt 0 ]] || classes=(interactive rag multiturn batch)
for c in "${classes[@]}"; do
  case "$c" in
    interactive) prof=interactive; rate="$INT_RATE" ;;
    rag)         prof=long-prompt; rate="$RAG_RATE" ;;
    multiturn)   prof=multi-turn;  rate="$MT_RATE" ;;
    batch)       prof="batch";       rate="$BATCH_RATE" ;;
    *) echo "classe inconnue : $c" >&2; continue ;;
  esac
  echo "== classe $c : profil $prof, débit $rate req/s ($(date +%T))"
  BENCH_KEY="lab-$c" PER_REQUEST=true RESULT_TAG="class${TAG:+-$TAG}" RATE="$rate" RAG_RATE="$rate" WARMUP="$WARMUP" DURATION="$DURATION" BENCH_TIMEOUT=1500 ./lab.sh bench "$prof"
  d="results/$(date +%Y-%m-%d)-${SCEN}-${prof}-class${TAG:+-$TAG}"
  python3 tests/run_window.py "$d" | tail -1
  python3 tests/goodput.py "$c" "$d" | tail -1
done
