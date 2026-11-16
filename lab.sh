#!/usr/bin/env bash
# lab.sh : pilotage du lab d'inférence (kind local et AKS). Idempotent, journaux horodatés.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$HOME/.local/bin:$PATH"
# shellcheck source=/dev/null
[[ -f "$ROOT/.env" ]] && { set -a; . "$ROOT/.env"; set +a; }

: "${PREFIX:=inflab}"
: "${AZ_LOCATION:=eastus}"
: "${GIT_REPO_URL:=https://github.com/ihsenalaya/inference.git}"
: "${GIT_REVISION:=main}"
KIND_NAME="${KIND_NAME:-lab}"
TF_DIR="$ROOT/infra/terraform"; export TF_DIR
ARGOCD_CHART_VERSION="$(awk '/argocdChart:/{gsub(/[{},]/,"");for(i=1;i<=NF;i++) if($i=="version:") print $(i+1)}' "$ROOT/gitops/root/versions.yaml")"

log()  { printf '%s [%s] %s\n' "$(date +%H:%M:%S)" "${1}" "${*:2}" >&2; }
die()  { log ERR "$*"; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "outil manquant : $1"; }

# kind : sous WSL le socket docker peut être périmé, on retombe sur kind.exe / docker.exe.
kind_cmd() { if docker ps >/dev/null 2>&1; then kind "$@"; else kind.exe "$@"; fi; }

kubeconfig_kind() {
  local f="${TMPDIR:-/tmp}/kubeconfig-kind-$KIND_NAME"
  kind_cmd get kubeconfig --name "$KIND_NAME" | tr -d '\r' >"$f"
  export KUBECONFIG="$f"
}

rand() { head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c "${1:-24}"; }

ensure_secrets() { # crée les secrets comme le fait Terraform sur Azure
  for ns in gateway monitoring inference argocd; do kubectl create ns "$ns" --dry-run=client -o yaml | kubectl apply -f - >/dev/null; done
  if ! kubectl -n gateway get secret litellm-secrets >/dev/null 2>&1; then
    local pg; pg="$(rand 24)"
    kubectl -n gateway create secret generic litellm-secrets \
      --from-literal=LITELLM_MASTER_KEY="sk-$(rand 32)" --from-literal=LITELLM_SALT_KEY="sk-$(rand 32)" \
      --from-literal=POSTGRES_PASSWORD="$pg" \
      --from-literal=DATABASE_URL="postgresql://litellm:${pg}@postgres.gateway.svc:5432/litellm"
  fi
  kubectl -n monitoring get secret grafana-admin >/dev/null 2>&1 || \
    kubectl -n monitoring create secret generic grafana-admin --from-literal=admin-user=admin --from-literal=admin-password="$(rand 20)"
  kubectl -n monitoring get secret alert-webhook >/dev/null 2>&1 || \
    kubectl -n monitoring create secret generic alert-webhook --from-literal=url="${ALERT_WEBHOOK_URL:-http://alert-sink.monitoring.svc:8080/}"
  kubectl -n inference get secret hf-token >/dev/null 2>&1 || \
    kubectl -n inference create secret generic hf-token --from-literal=HF_TOKEN="${HF_TOKEN:-}"
}

cmd_kind_up() {
  need helm; need kubectl
  if ! kind_cmd get clusters 2>/dev/null | grep -qx "$KIND_NAME"; then
    log INFO "création du cluster kind $KIND_NAME"
    local cfg; cfg="$(mktemp --suffix=.yaml)"
    cat >"$cfg" <<'YAML'
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    image: kindest/node:v1.35.0
YAML
    local cfgw; cfgw="$cfg"; command -v wslpath >/dev/null && ! docker ps >/dev/null 2>&1 && cfgw="$(wslpath -w "$cfg")"
    kind_cmd create cluster --name "$KIND_NAME" --config "$cfgw" --wait 180s
  fi
  kubeconfig_kind
  ensure_secrets
  helm upgrade --install argocd argo-cd --repo https://argoproj.github.io/argo-helm --version "$ARGOCD_CHART_VERSION" \
    -n argocd --create-namespace -f "$ROOT/gitops/bootstrap/argocd-values.yaml" --wait --timeout 10m
  helm upgrade --install root "$ROOT/gitops/bootstrap/root-app" -n argocd \
    --set repoURL="$GIT_REPO_URL" --set revision="${GIT_REVISION}" --set env=kind --set scenario="${SCENARIO:-kind-mock}" \
    --set-string disable="${KIND_DISABLE//,/\\,}" --wait
  log INFO "application racine créée ; suivre : $0 status"
}

cmd_kind_down() { kind_cmd delete cluster --name "$KIND_NAME"; }

cmd_status() {
  [[ -n "${KUBECONFIG:-}" ]] || kubeconfig_kind 2>/dev/null || true
  kubectl get nodes -o wide || true
  echo; kubectl -n argocd get applications.argoproj.io -o custom-columns=NAME:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status,WAVE:.metadata.annotations.argocd\\.argoproj\\.io/sync-wave 2>/dev/null | sort -k4 -n || true
  echo; kubectl get llminferenceservices -A 2>/dev/null || true
  echo; kubectl get gateway -A 2>/dev/null || true
}

main() {
  local c="${1:-help}"; shift || true
  case "$c" in
    kind-up) cmd_kind_up "$@" ;;
    kind-down) cmd_kind_down "$@" ;;
    status) cmd_status "$@" ;;
    help|*) echo "usage: $0 {kind-up|kind-down|status|...}"; [[ "$c" == help ]] || exit 1 ;;
  esac
}
main "$@"
