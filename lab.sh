#!/usr/bin/env bash
# lab.sh : pilotage du lab d'inférence (AKS avec T4, et kind local pour les tests).
#
# L'infrastructure et le GitOps sont 100 % déclaratifs (Terraform + Argo CD) : ce script ne fait
# que les enchaîner et offrir des raccourcis (benchs, ports, arrêt, destruction). Idempotent,
# journaux horodatés, timeouts explicites, codes de retour fiables.
# shellcheck disable=SC2015,SC2016
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$HOME/.local/bin:$PATH"
# shellcheck source=/dev/null
[[ -f "$ROOT/.env" ]] && { set -a; . "$ROOT/.env"; set +a; }

: "${PREFIX:=inflab}"
: "${AZ_LOCATION:=eastus}"
: "${AZ_SUBSCRIPTION_ID:=}"
: "${GIT_REPO_URL:=https://github.com/ihsenalaya/inference.git}"
: "${GIT_REVISION:=main}"
: "${GPU_HOURLY_PRICE:=0.526}"
: "${SYSTEM_HOURLY_PRICE:=0.182}"
KIND_NAME="${KIND_NAME:-lab}"
TF_DIR="$ROOT/infra/terraform"
RG="${PREFIX}-rg"
AKS="${PREFIX}-aks"
TIMEOUT_SYNC="${TIMEOUT_SYNC:-3600}"   # attente de convergence Argo CD (s) : nœud GPU, driver, images de plusieurs Go

log()  { printf '%s [%s] %s\n' "$(date +%H:%M:%S)" "$1" "${*:2}" >&2; }
die()  { log ERR "$*"; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "outil manquant : $1"; }

# ----------------------------------------------------------------------------- kind
# Sous WSL le socket docker peut être périmé : on retombe sur kind.exe / docker.exe.
kind_cmd() { if docker ps >/dev/null 2>&1; then kind "$@"; else kind.exe "$@"; fi; }

kubeconfig_kind() {
  local f="${TMPDIR:-/tmp}/kubeconfig-kind-$KIND_NAME"
  kind_cmd get kubeconfig --name "$KIND_NAME" | tr -d '\r' >"$f"
  export KUBECONFIG="$f"
}

rand() { head -c 96 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c "${1:-24}"; }

# Sur kind, les secrets sont créés ici (sur Azure c'est Terraform qui les crée, mêmes noms).
ensure_secrets_kind() {
  local ns
  for ns in gateway monitoring inference argocd; do
    kubectl create ns "$ns" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
  done
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

argocd_chart_version() {
  awk '/argocdChart:/{gsub(/[{},]/,""); for(i=1;i<=NF;i++) if($i=="version:") print $(i+1)}' "$ROOT/gitops/root/versions.yaml"
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
    local cfgw="$cfg"
    if command -v wslpath >/dev/null && ! docker ps >/dev/null 2>&1; then cfgw="$(wslpath -w "$cfg")"; fi
    kind_cmd create cluster --name "$KIND_NAME" --config "$cfgw" --wait 180s
  fi
  kubeconfig_kind
  kubectl label node --all workload=platform --overwrite >/dev/null   # comme le pool système AKS (le banc de charge s'y exécute)
  ensure_secrets_kind
  helm upgrade --install argocd argo-cd --repo https://argoproj.github.io/argo-helm --version "$(argocd_chart_version)" \
    -n argocd --create-namespace -f "$ROOT/gitops/bootstrap/argocd-values.yaml" --wait --timeout 10m
  helm upgrade --install root "$ROOT/gitops/bootstrap/root-app" -n argocd \
    --set repoURL="$GIT_REPO_URL" --set revision="$GIT_REVISION" --set env=kind \
    --set scenario="${SCENARIO:-}" --set-string disable="${KIND_DISABLE//,/\\,}" --wait
  log INFO "application racine créée ; suivre : $0 status"
}

cmd_kind_down() { kind_cmd delete cluster --name "$KIND_NAME"; }

# ----------------------------------------------------------------------------- azure
az_ok() { az account show >/dev/null 2>&1 || die "session az absente : az login"; }

tf() {
  terraform -chdir="$TF_DIR" "$@"
}

tf_vars() {
  TF_VARS=(-var "subscription_id=${AZ_SUBSCRIPTION_ID}" -var "location=${AZ_LOCATION}" -var "prefix=${PREFIX}"
           -var "git_repo_url=${GIT_REPO_URL}" -var "git_revision=${GIT_REVISION}"
           -var "gpu_node_count=${GPU_NODES:-1}" -var "gpu_hourly_price=${GPU_HOURLY_PRICE}")
  [[ -n "${HF_TOKEN:-}" ]] && TF_VARS+=(-var "hf_token=${HF_TOKEN}")
  [[ -n "${ALERT_WEBHOOK_URL:-}" ]] && TF_VARS+=(-var "alert_webhook_url=${ALERT_WEBHOOK_URL}")
  [[ -n "${MY_IP_CIDR:-}" ]] && TF_VARS+=(-var "api_server_authorized_cidrs=[\"${MY_IP_CIDR}\"]")
  return 0
}

kubeconfig_aks() {
  # az (Windows sous WSL) ne sait pas écrire dans /tmp : on récupère le kubeconfig sur stdout.
  local f="${TMPDIR:-/tmp}/kubeconfig-aks-$PREFIX"
  az aks get-credentials -g "$RG" -n "$AKS" --overwrite-existing --file - | tr -d '\r' >"$f"
  chmod 600 "$f"
  export KUBECONFIG="$f"
}

use_cluster() { # cluster courant : AKS si le RG existe, sinon kind
  if [[ -n "${KUBECONFIG:-}" ]] && kubectl get nodes >/dev/null 2>&1; then return 0; fi
  if [[ "${LAB_TARGET:-}" == kind ]]; then kubeconfig_kind; return 0; fi
  if az group exists -n "$RG" 2>/dev/null | grep -q true; then kubeconfig_aks; else kubeconfig_kind; fi
}

cmd_preflight() {
  local bad=0 t
  for t in az kubectl helm terraform git gh; do
    if command -v "$t" >/dev/null 2>&1; then log OK "$t présent"; else log ERR "$t manquant"; bad=1; fi
  done
  [[ -n "$AZ_SUBSCRIPTION_ID" ]] || { log ERR "AZ_SUBSCRIPTION_ID vide (.env)"; bad=1; }
  az_ok
  local cur; cur="$(az account show --query id -o tsv | tr -d '\r')"
  [[ "$cur" == "$AZ_SUBSCRIPTION_ID" ]] && log OK "abonnement $cur" || { log ERR "abonnement actif $cur != $AZ_SUBSCRIPTION_ID : az account set -s $AZ_SUBSCRIPTION_ID"; bad=1; }
  # SKU GPU disponible dans la région
  local restr
  restr="$(az vm list-skus -l "$AZ_LOCATION" --size Standard_NC4as_T4_v3 --query "[0].restrictions[0].reasonCode" -o tsv 2>/dev/null | tr -d '\r')"
  if [[ -z "$restr" || "$restr" == None ]]; then log OK "SKU Standard_NC4as_T4_v3 disponible en $AZ_LOCATION"; else log ERR "SKU T4 restreint : $restr"; bad=1; fi
  # Quota famille NCASv3_T4 (4 vCPU par nœud)
  local need=$(( ${GPU_NODES:-1} * 4 )) limit used
  read -r used limit < <(az vm list-usage -l "$AZ_LOCATION" --query "[?contains(name.value,'NCASv3_T4')].[currentValue,limit]" -o tsv | tr -d '\r')
  if [[ "${limit:-0}" -ge $(( ${used:-0} + need )) ]]; then log OK "quota T4 : ${used}/${limit} vCPU (besoin +$need)"; else log ERR "quota T4 insuffisant : ${used:-?}/${limit:-?} (besoin +$need)"; bad=1; fi
  local sys_limit
  sys_limit="$(az vm list-usage -l "$AZ_LOCATION" --query "[?name.value=='StandardDasv7Family'].limit" -o tsv | tr -d '\r')"
  [[ "${sys_limit:-0}" -ge 4 ]] && log OK "quota Dasv7 : $sys_limit vCPU" || { log ERR "quota Dasv7 insuffisant ($sys_limit)"; bad=1; }
  local p
  for p in Microsoft.ContainerService Microsoft.Compute Microsoft.Network; do
    az provider show -n "$p" --query registrationState -o tsv | tr -d '\r' | grep -qx Registered && log OK "provider $p" || { log ERR "provider $p non enregistré"; bad=1; }
  done
  # Garde-fou : le lab ne touche qu'à son groupe de ressources (jamais aux snapshots)
  log INFO "périmètre : groupe de ressources $RG uniquement (aucun snapshot)"
  [[ $bad -eq 0 ]] && log OK "preflight : tout est bon" || die "preflight : problèmes détectés"
}

cmd_cost() {
  local g="${GPU_NODES:-1}"
  awk -v g="$g" -v gp="$GPU_HOURLY_PRICE" -v sp="$SYSTEM_HOURLY_PRICE" 'BEGIN{
    h=g*gp+sp; printf "Coût estimé : %d nœud(s) T4 x %.3f + 1 système x %.3f = %.3f $/h (%.2f $/jour) + disques, IP, réseau (négligeables)\n", g, gp, sp, h, h*24 }'
}

cmd_up() {
  need terraform; need kubectl; need helm; az_ok
  [[ -n "$AZ_SUBSCRIPTION_ID" ]] || die "AZ_SUBSCRIPTION_ID vide (.env)"
  tf_vars
  cmd_cost
  tf init -input=false
  local t0; t0="$(date +%s)"
  if ! tf apply -input=false -auto-approve "${TF_VARS[@]}" 2>&1 | tee "${TMPDIR:-/tmp}/tf-apply.log"; then
    if grep -qiE 'AllocationFailed|OverconstrainedAllocationRequest|ZonalAllocationFailed' "${TMPDIR:-/tmp}/tf-apply.log"; then
      die "capacité T4 indisponible en $AZ_LOCATION (AllocationFailed) malgré le quota : réessayer plus tard ou changer AZ_LOCATION (le quota T4 n'existe qu'en eastus sur cet abonnement)"
    fi
    die "terraform apply a échoué (voir ${TMPDIR:-/tmp}/tf-apply.log)"
  fi
  log INFO "terraform apply : $(( $(date +%s) - t0 )) s"
  kubeconfig_aks
  wait_argocd
  wait_workloads
  cmd_smoke
}

apps_not_ready() {
  kubectl -n argocd get applications.argoproj.io --no-headers 2>/dev/null | awk '$2!="Synced" || $3!="Healthy" {printf "%s:%s/%s ", $1, $2, $3}'
}

wait_argocd() {
  log INFO "attente de convergence Argo CD (max ${TIMEOUT_SYNC}s)"
  local end=$(( $(date +%s) + TIMEOUT_SYNC )) bad
  while [[ $(date +%s) -lt $end ]]; do
    bad="$(apps_not_ready)"
    if [[ -z "$bad" ]] && [[ "$(kubectl -n argocd get applications.argoproj.io --no-headers 2>/dev/null | wc -l)" -ge 15 ]]; then
      log OK "toutes les applications Argo CD sont Synced et Healthy"; return 0
    fi
    log INFO "en attente : ${bad:-aucune application}"
    sleep 30
  done
  die "Argo CD n'a pas convergé dans le délai : $bad"
}

# Les statuts Argo CD / KServe sont périmés juste après un `az aks start` : on vérifie l'état réel des pods.
workloads_ready() {
  kubectl get nodes --no-headers 2>/dev/null | awk '$2!="Ready"{bad=1} END{exit bad}' || return 1
  local g; g="$(kubectl get nodes -l workload=inference -o jsonpath='{range .items[*]}{.status.allocatable.nvidia\.com/gpu}{"\n"}{end}' 2>/dev/null | grep -c '^1$')" || true
  [[ "$g" -ge "${GPU_NODES:-1}" ]] || return 1
  local ns
  for ns in inference gateway monitoring; do
    kubectl -n "$ns" get pods --no-headers 2>/dev/null | awk '$3!="Completed" { split($2, a, "/"); if (a[1] != a[2] || $3 != "Running") bad=1 } END{exit bad}' || return 1
  done
  [[ "$(kubectl -n inference get pods -l kserve.io/component=workload --no-headers 2>/dev/null | grep -c ' 1/1 ')" -ge 1 ]]
}

wait_workloads() {
  log INFO "attente des pods (nœuds, GPU, vLLM, LiteLLM...) max ${TIMEOUT_SYNC}s"
  local end=$(( $(date +%s) + TIMEOUT_SYNC ))
  while [[ $(date +%s) -lt $end ]]; do
    if workloads_ready; then log OK "tous les pods sont prêts"; return 0; fi
    sleep 20
  done
  die "les pods ne sont pas tous prêts dans le délai"
}

cmd_status() {
  use_cluster
  kubectl get nodes -o wide || true
  echo
  kubectl get nodes -o custom-columns='NODE:.metadata.name,GPU:.status.allocatable.nvidia\.com/gpu,CPU:.status.allocatable.cpu,MEM:.status.allocatable.memory' || true
  echo
  kubectl -n argocd get applications.argoproj.io -o custom-columns='NAME:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status,WAVE:.metadata.annotations.argocd\.argoproj\.io/sync-wave' 2>/dev/null | sort -k4 -n || true
  echo
  kubectl get llminferenceservices -A 2>/dev/null || true
  echo
  kubectl get gateway -A 2>/dev/null || true
  echo
  kubectl -n inference get scaledobject,hpa 2>/dev/null || true
}

# ----------------------------------------------------------------------------- smoke
PASS=0; FAILN=0
check() { # description, commande...
  local d="$1"; shift
  if "$@" >/dev/null 2>&1; then log OK "$d"; PASS=$((PASS+1)); else log ERR "$d"; FAILN=$((FAILN+1)); fi
}

litellm_key() { kubectl -n gateway get secret litellm-keys -o jsonpath="{.data.${1:-lab-bench}}" | base64 -d; }

with_pf() { # port-forward temporaire : with_pf ns svc local remote -- commande...
  local ns="$1" svc="$2" lp="$3" rp="$4"; shift 5
  kubectl -n "$ns" port-forward "svc/$svc" "$lp:$rp" >/dev/null 2>&1 &
  local pid=$!
  for _ in $(seq 1 20); do (echo >"/dev/tcp/127.0.0.1/$lp") 2>/dev/null && break; sleep 1; done   # attend le port (évite la course au démarrage)
  local rc=0; "$@" || rc=$?
  kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true
  return $rc
}

chat_ok() { # port clé modèle température [stream]
  local out stream="${5:-false}"
  out="$(curl -fsS -m 120 "http://127.0.0.1:$1/v1/chat/completions" -H "Authorization: Bearer $2" -H 'Content-Type: application/json' \
    -d "{\"model\":\"$3\",\"temperature\":$4,\"max_tokens\":48,\"stream\":$stream,\"messages\":[{\"role\":\"user\",\"content\":\"Explique en deux phrases ce qu'est un GPU.\"}]}")" || return 1
  [[ "$stream" == true ]] && grep -q '\[DONE\]' <<<"$out" && return 0
  python3 - "$out" <<'PY'
import json, os, sys
d = json.loads(sys.argv[1])
t = d["choices"][0]["message"]["content"].strip()
if os.environ.get("SMOKE_MOCK") == "1":
    sys.exit(0 if t else 1)   # faux vLLM (kind) : la sortie est volontairement répétitive
# sortie cohérente : non vide, pas dégénérée (un même mot répété plus de 60 % du temps)
w = t.split()
assert len(w) >= 3, "sortie trop courte"
assert max(w.count(x) for x in set(w)) / len(w) < 0.6, "sortie dégénérée"
PY
}

cmd_smoke() {
  use_cluster; PASS=0; FAILN=0
  local alias
  case "$(active_scenario)" in kind-*) export SMOKE_MOCK=1 ;; esac
  check "Argo CD : toutes les applications Synced/Healthy" bash -c "! kubectl -n argocd get applications.argoproj.io --no-headers | awk '\$2!=\"Synced\"||\$3!=\"Healthy\"' | grep -q ."
  check "Gateway programmée" bash -c "kubectl -n inference get gateway inference-gateway -o jsonpath='{.status.conditions[?(@.type==\"Programmed\")].status}' | grep -q True"
  check "LLMInferenceService prêts" bash -c "! kubectl -n inference get llminferenceservices --no-headers | awk '\$3!=\"True\"' | grep -q ."
  if kubectl get nodes -o jsonpath='{.items[*].status.allocatable.nvidia\.com/gpu}' | grep -q '[0-9]'; then
    check "chaque nœud GPU annonce nvidia.com/gpu: 1" bash -c "kubectl get nodes -l workload=inference -o jsonpath='{range .items[*]}{.status.allocatable.nvidia\\.com/gpu}{\"\\n\"}{end}' | grep -vx 1 | grep -q . && exit 1 || exit 0"
  fi
  # chemin complet par LiteLLM, en streaming et sans, à deux températures (test de bon sens B5)
  local key; key="$(litellm_key lab-bench 2>/dev/null || true)"
  if [[ -n "$key" ]]; then
    for alias in $(kubectl -n gateway get cm litellm-config -o jsonpath='{.data.config\.yaml}' | awk '/model_name:/{print $3}'); do
      with_pf gateway litellm 14000 4000 -- chat_ok 14000 "$key" "$alias" 0 && { log OK "chat $alias (T=0)"; PASS=$((PASS+1)); } || { log ERR "chat $alias (T=0)"; FAILN=$((FAILN+1)); }
      with_pf gateway litellm 14000 4000 -- chat_ok 14000 "$key" "$alias" 0.7 && { log OK "chat $alias (T=0.7)"; PASS=$((PASS+1)); } || { log ERR "chat $alias (T=0.7)"; FAILN=$((FAILN+1)); }
      with_pf gateway litellm 14000 4000 -- chat_ok 14000 "$key" "$alias" 0 true && { log OK "chat $alias (streaming)"; PASS=$((PASS+1)); } || { log ERR "chat $alias (streaming)"; FAILN=$((FAILN+1)); }
    done
  else
    log WARN "clé LiteLLM absente : tests de chat ignorés"
  fi
  if kubectl -n monitoring get svc kps-prometheus >/dev/null 2>&1; then
    check "Prometheus : aucune cible lab en échec" with_pf monitoring kps-prometheus 19090 9090 -- bash -c "curl -fsS 'http://127.0.0.1:19090/api/v1/targets?state=active' | python3 -c \"import sys,json; d=json.load(sys.stdin)['data']['activeTargets']; bad=[t['scrapePool'] for t in d if 'lab-' in t['scrapePool'] and t['health']!='up']; print(bad); sys.exit(1 if bad else 0)\""
    check "Prometheus : règles lab chargées et saines" with_pf monitoring kps-prometheus 19090 9090 -- bash -c "curl -fsS http://127.0.0.1:19090/api/v1/rules | python3 -c \"import sys,json; g=[x for x in json.load(sys.stdin)['data']['groups'] if x['name'].startswith('lab.')]; sys.exit(0 if g and all(r['health']=='ok' for x in g for r in x['rules']) else 1)\""
  fi
  log INFO "smoke : $PASS ok, $FAILN en échec"
  [[ $FAILN -eq 0 ]]
}

# ----------------------------------------------------------------------------- scénarios, bench
current_env() { if kubectl -n argocd get application root -o jsonpath='{.spec.source.helm.parameters[?(@.name=="env")].value}' 2>/dev/null | grep -q kind; then echo kind; else echo azure; fi; }

cmd_scenario() {
  local s="${1:-}"; [[ -n "$s" ]] || die "usage : $0 scenario <nom> (voir gitops/scenarios/)"
  [[ -f "$ROOT/gitops/scenarios/$s.yaml" ]] || die "scénario inconnu : $s"
  use_cluster
  local e; e="$(current_env)"
  printf '# Scénario actif (%s). Modifié par `lab.sh scenario`, appliqué par Argo CD.\nscenario: %s\n' "$e" "$s" >"$ROOT/gitops/active-$e.yaml"
  git -C "$ROOT" add "gitops/active-$e.yaml"
  git -C "$ROOT" commit -q -m "Scénario actif ($e) : $s" || true
  git -C "$ROOT" push -q origin "$GIT_REVISION"
  kubectl -n argocd annotate application root argocd.argoproj.io/refresh=hard --overwrite >/dev/null
  log INFO "scénario $s poussé ; Argo CD synchronise (suivre : $0 status)"
}

active_scenario() { kubectl -n inference get llminferenceservices -o jsonpath='{.items[0].metadata.labels.lab/scenario}' 2>/dev/null || echo unknown; }

grafana_annotation() { # texte tags
  local pw; pw="$(kubectl -n monitoring get secret grafana-admin -o jsonpath='{.data.admin-password}' | base64 -d)"
  with_pf monitoring kube-prometheus-stack-grafana 13000 80 -- curl -fsS -m 15 -u "admin:$pw" -H 'Content-Type: application/json' \
    -d "{\"text\":\"$1\",\"tags\":[$2]}" http://127.0.0.1:13000/api/annotations >/dev/null 2>&1 || log WARN "annotation Grafana non posée"
}

cmd_bench() {
  local profile="${1:-}"; shift || true
  [[ -n "$profile" ]] || die "usage : $0 bench <smoke|sweep|steady|shared-prefix|multi-turn|long-prompt|burst> [--target litellm|gateway|direct] [--model alias]"
  local target=litellm model=""
  while [[ $# -gt 0 ]]; do case "$1" in --target) target="$2"; shift 2 ;; --model) model="$2"; shift 2 ;; *) die "option inconnue $1" ;; esac; done
  [[ -f "$ROOT/gitops/bench/profiles/$profile.yaml" ]] || die "profil inconnu : $profile"
  use_cluster
  local scen sha ts name key base apipath
  scen="$(active_scenario)"; sha="$(git -C "$ROOT" rev-parse --short HEAD)"; ts="$(date +%Y%m%d-%H%M%S)"
  name="bench-${profile}-${ts}"; name="${name,,}"
  local alias_name hf_name res_name
  alias_name="${model:-$(kubectl -n gateway get cm litellm-config -o jsonpath='{.data.config\.yaml}' | awk '/model_name:/{print $3; exit}')}"
  hf_name="$(kubectl -n inference get llminferenceservices -o jsonpath='{range .items[*]}{.metadata.labels.lab/alias}{" "}{.spec.model.name}{" "}{.metadata.name}{"\n"}{end}' | awk -v a="$alias_name" '$1==a{print $2}')"
  res_name="$(kubectl -n inference get llminferenceservices -o jsonpath='{range .items[*]}{.metadata.labels.lab/alias}{" "}{.spec.model.name}{" "}{.metadata.name}{"\n"}{end}' | awk -v a="$alias_name" '$1==a{print $3}')"
  if [[ "$target" == litellm ]]; then
    key="$(litellm_key "${BENCH_KEY:-lab-bench}")"; base="http://litellm.gateway.svc:4000"; apipath=""
    model="$alias_name"
  elif [[ "$target" == direct ]]; then
    # directement le Service de vLLM (sans LiteLLM, Gateway ni EPP) : mesures du GPU seul, ou Gateway indisponible
    key=""; base="http://${res_name}-kserve-workload-svc.inference.svc.cluster.local:8000"; apipath=""; model="$hf_name"
  else
    key=""; base="http://inference-gateway-istio.inference.svc.cluster.local"; apipath="/inference/${res_name}"; model="$hf_name"
  fi
  local extra=()
  [[ -n "${RATE:-}" ]] && extra+=(--set "rate=$RATE")
  [[ -n "${DURATION:-}" ]] && extra+=(--set "duration=$DURATION")
  [[ -n "${SWEEP_RATES:-}" ]] && extra+=(--set "sweepRates={${SWEEP_RATES}}")
  [[ -n "${WARMUP:-}" ]] && extra+=(--set "warmup=$WARMUP")
  [[ -n "${PER_REQUEST:-}" ]] && extra+=(--set "perRequest=$PER_REQUEST")
  [[ -n "${RAG_RATE:-}" ]] && extra+=(--set "ragRate=$RAG_RATE")
  [[ -n "${STAGE_DURATION:-}" ]] && extra+=(--set "stageDuration=$STAGE_DURATION")
  log INFO "bench $profile sur $scen (cible $target, modèle $model)"
  grafana_annotation "bench $profile début | scénario $scen | git $sha | cible $target" '"bench","start"'
  helm template bench "$ROOT/gitops/bench" --set profile="$profile" --set name="$name" --set baseUrl="$base" --set apiPath="$apipath" \
    --set apiKey="$key" --set model="$model" --set prometheusUrl="${BENCH_PROM_URL-http://kps-prometheus.monitoring.svc:9090}" --set tokenizerModel="${hf_name:-$model}" "${extra[@]}" | kubectl apply -f - >/dev/null
  local out; out="$ROOT/results/$(date +%Y-%m-%d)-${scen}-${profile}"; [[ "$target" == litellm ]] || out="${out}-${target}"; [[ -z "${RESULT_TAG:-}" ]] || out="${out}-${RESULT_TAG}"; mkdir -p "$out"
  # attend la fin OU l'échec du job (un job en échec ne doit pas faire attendre tout le délai)
  local bend=$(( $(date +%s) + ${BENCH_TIMEOUT:-3600} )) bst
  while [[ $(date +%s) -lt $bend ]]; do
    bst="$(kubectl -n inference get "job/$name" -o jsonpath='{range .status.conditions[*]}{.type}={.status} {end}' 2>/dev/null || true)"
    case "$bst" in *Complete=True*) break ;; *Failed=True*) log ERR "le job de bench a échoué"; break ;; esac
    sleep 10
  done
  kubectl -n inference logs "job/$name" >"$out/run.log" 2>&1 || true
  python3 - "$out" <<'PY'
import pathlib, re, sys
out = pathlib.Path(sys.argv[1]); log = (out / "run.log").read_text()
m = re.search(r"===LAB-RESULTS-BEGIN===\n(.*)===LAB-RESULTS-END===", log, re.S)
if m:
    files, cur = {}, None
    for line in m.group(1).splitlines(keepends=True):
        if line.startswith("=== FILE "):
            cur = line[9:].strip(); files[cur] = []
        elif cur is not None:
            files[cur].append(line)
    for name, lines in files.items():   # une seule écriture par fichier (sous WSL, ouvrir un fichier par ligne prend des dizaines de minutes)
        f = out / name; f.parent.mkdir(parents=True, exist_ok=True); f.write_text("".join(lines))
    if len(log) > 2_000_000:   # les fichiers sont extraits : le journal n'a plus besoin de les contenir
        (out / "run.log").write_text(log[:m.start()] + "[résultats extraits dans ce dossier]\n")
PY
  # la clé virtuelle ne doit jamais atterrir dans Git : masquage dans tous les fichiers du run
  [[ -z "$key" ]] || grep -rlF -- "$key" "$out" 2>/dev/null | xargs -r sed -i "s/${key//\//\\/}/REDACTED/g"
  grafana_annotation "bench $profile fin" '"bench","end"'
  printf '{"profile":"%s","scenario":"%s","git":"%s","target":"%s","model":"%s","date":"%s"}\n' "$profile" "$scen" "$sha" "$target" "$model" "$(date -Is)" >"$out/meta.json"
  bench_summary "$out"
}

bench_summary() {
  python3 - "$1" <<'PY'
import json, pathlib, sys
out = pathlib.Path(sys.argv[1])
f = next(iter(sorted(out.rglob("summary_lifecycle_metrics.json"))), None)
if not f:
    print("pas de résumé trouvé : voir", out / "run.log"); sys.exit(0)
d = json.loads(f.read_text()); s = d.get("successes", d)
def g(*ks):
    x = s
    for k in ks:
        x = x.get(k, {}) if isinstance(x, dict) else {}
    return x if not isinstance(x, dict) else x.get("mean")
print("résumé :", f.relative_to(out))
for label, key in (("TTFT (s)", "time_to_first_token"), ("TPOT (s)", "time_per_output_token"), ("latence (s)", "request_latency")):
    v = s.get("latency", {}).get(key, {})
    if isinstance(v, dict) and v:
        print(f"  {label:12} moyenne={v.get('mean')} p50={v.get('median')} p99={v.get('p99')}")
tp = s.get("throughput", {})
if tp: print("  débit       ", {k: tp[k] for k in list(tp)[:4]})
print("  erreurs     ", d.get("failures", {}).get("count", 0))
PY
}

# ----------------------------------------------------------------------------- ui, gpu, stop/start, down
# Minutes d'inactivité GPU : le GPU est « inactif » s'il n'y a ni requête vLLM en cours ni utilisation GPU > 1 %.
gpu_idle_minutes() {
  with_pf monitoring kps-prometheus 19092 9090 -- python3 - <<'PY'
import json, urllib.parse, urllib.request
def q(e):
    u = "http://127.0.0.1:19092/api/v1/query?" + urllib.parse.urlencode({"query": e})
    r = json.load(urllib.request.urlopen(u, timeout=20))["data"]["result"]
    return float(r[0]["value"][1]) if r else None
# plus grand m (minutes) tel que max(utilisation GPU) sur m minutes reste < 1 % : recherche par paliers
for m in (240, 120, 60, 30, 15, 10, 5, 0):
    if m == 0:
        print(0); break
    v = q(f"max_over_time(max(DCGM_FI_DEV_GPU_UTIL)[{m}m:1m])")
    w = q(f"max_over_time(sum(vllm:num_requests_running)[{m}m:1m])")
    if v is not None and v < 1 and (w or 0) == 0:
        print(m); break
PY
}

# lab.sh idle [--stop-after MINUTES] : affiche l'inactivité du GPU ; avec --stop-after, arrête le cluster au-delà du seuil.
# À lancer à la main ou par cron : rien ne s'arrête tout seul sans que vous l'ayez demandé.
cmd_idle() {
  local stop_after=""
  [[ "${1:-}" == "--stop-after" ]] && stop_after="${2:?minutes}"
  use_cluster
  local m; m="$(gpu_idle_minutes || echo 0)"
  log INFO "GPU inactif depuis au moins ${m} min (paliers testés : 5, 10, 15, 30, 60, 120, 240)"
  if [[ -n "$stop_after" && "${m:-0}" -ge "$stop_after" ]]; then
    log WARN "inactivité >= ${stop_after} min : arrêt du cluster"
    cmd_stop
  fi
}

# lab.sh snapshot-metrics [heures] : sauvegarde dans results/ l'historique des règles lab:* et de quelques métriques DCGM.
# Prometheus vit sur un disque du cluster : sans cet export, les courbes disparaissent avec `down`.
cmd_snapshot_metrics() {
  local hours="${1:-12}"
  use_cluster
  local out; out="$ROOT/results/metrics-$(date +%Y%m%d-%H%M%S)"; mkdir -p "$out"
  with_pf monitoring kps-prometheus 19093 9090 -- python3 - "$out" "$hours" <<'PY'
import json, pathlib, sys, time, urllib.parse, urllib.request
out, hours = pathlib.Path(sys.argv[1]), float(sys.argv[2])
B = "http://127.0.0.1:19093/api/v1"
def get(path, **p):
    return json.load(urllib.request.urlopen(f"{B}/{path}?" + urllib.parse.urlencode(p), timeout=60))["data"]
names = [n for n in get("label/__name__/values") if n.startswith(("lab:", "DCGM_FI_DEV_GPU_UTIL", "DCGM_FI_DEV_POWER_USAGE", "DCGM_FI_DEV_FB_USED", "DCGM_FI_PROF_"))]
end = time.time(); start = end - hours * 3600
saved = 0
for n in names:
    r = get("query_range", query=n, start=start, end=end, step=60)["result"]
    if r:
        (out / (n.replace(":", "_") + ".json")).write_text(json.dumps(r))
        saved += 1
print(f"{saved} séries sauvegardées dans {out}")
PY
}

cmd_ui() {
  use_cluster
  local gp ap lk
  gp="$(kubectl -n monitoring get secret grafana-admin -o jsonpath='{.data.admin-password}' | base64 -d)"
  ap="$(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' 2>/dev/null | base64 -d || true)"
  lk="$(kubectl -n gateway get secret litellm-secrets -o jsonpath='{.data.LITELLM_MASTER_KEY}' | base64 -d)"
  kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 3000:80 >/dev/null 2>&1 &
  kubectl -n monitoring port-forward svc/kps-prometheus 9090:9090 >/dev/null 2>&1 &
  kubectl -n monitoring port-forward svc/kps-alertmanager 9093:9093 >/dev/null 2>&1 &
  kubectl -n argocd port-forward svc/argocd-server 8080:80 >/dev/null 2>&1 &
  kubectl -n gateway port-forward svc/litellm 4000:4000 >/dev/null 2>&1 &
  cat <<EOF
Grafana       http://localhost:3000   admin / $gp
Prometheus    http://localhost:9090
Alertmanager  http://localhost:9093
Argo CD       http://localhost:8080   admin / ${ap:-<secret initial supprimé>}
LiteLLM       http://localhost:4000   (master key : $lk)
Ctrl-C pour fermer les port-forwards.
EOF
  trap 'kill $(jobs -p) 2>/dev/null' EXIT
  wait
}

cmd_gpu_scale() {
  local n="${1:-}"; [[ "$n" =~ ^[0-2]$ ]] || die "usage : $0 gpu-scale <0|1|2>"
  az_ok; GPU_NODES="$n"; tf_vars; cmd_cost
  tf apply -input=false -auto-approve "${TF_VARS[@]}"
}

cmd_stop() {
  az_ok
  log INFO "arrêt du cluster AKS (les VM sont désallouées : plus de facturation de calcul)"
  az aks stop -g "$RG" -n "$AKS"
  az aks show -g "$RG" -n "$AKS" --query powerState.code -o tsv
}

cmd_start() {
  az_ok
  log INFO "démarrage du cluster AKS"
  if ! az aks start -g "$RG" -n "$AKS" 2>"${TMPDIR:-/tmp}/aks-start.err"; then
    if grep -qiE 'AllocationFailed|OverconstrainedAllocationRequest|ZonalAllocationFailed' "${TMPDIR:-/tmp}/aks-start.err"; then
      die "capacité T4 indisponible au redémarrage (AllocationFailed) : réessayer plus tard ; en dernier recours $0 down puis $0 up"
    fi
    die "az aks start a échoué : $(cat "${TMPDIR:-/tmp}/aks-start.err")"
  fi
  kubeconfig_aks
  wait_argocd
  wait_workloads
  cmd_smoke
}

cmd_down() {
  local yes=false; [[ "${1:-}" == "--yes" ]] && yes=true
  az_ok
  if [[ $yes != true ]]; then
    read -r -p "Détruire TOUT le lab ($RG, AKS, nœuds GPU) ? taper 'oui' : " a; [[ "$a" == oui ]] || die "annulé"
  fi
  tf_vars
  # Le cluster disparaît avec le groupe de ressources : inutile (et lent, voire bloquant : finalisateurs Argo CD) de désinstaller
  # un à un les objets Helm/Kubernetes. On les retire de l'état puis on détruit l'infrastructure Azure.
  local r
  for r in $(tf state list 2>/dev/null | grep -E '^(helm_release|kubernetes_)'); do tf state rm "$r" >/dev/null; done
  # Un échec transitoire (ResourceGroupDeletionBlocked : mise à jour de plateforme du VMSS en cours) se résout en réessayant.
  local attempt
  for attempt in 1 2 3 4; do
    tf destroy -input=false -auto-approve "${TF_VARS[@]}" && break
    [[ $attempt -lt 4 ]] || die "terraform destroy a échoué 4 fois"
    log WARN "destroy échoué (tentative $attempt), nouvelle tentative dans 120 s"; sleep 120
  done
  if az group exists -n "$RG" | grep -q true; then
    log WARN "le groupe $RG existe encore, suppression"
    az group delete -n "$RG" --yes
  fi
  # le groupe de nœuds est supprimé avec le cluster ; vérification
  az group exists -n "${PREFIX}-aks-nodes" | grep -q true && die "groupe de nœuds ${PREFIX}-aks-nodes encore présent"
  log OK "rien ne reste de la solution sur Azure (ressources facturées : aucune)"
  kubectl config delete-context "$AKS" >/dev/null 2>&1 || true
}

cmd_versions() {
  echo "== versions épinglées (gitops/root/versions.yaml)"
  python3 - "$ROOT/gitops/root/versions.yaml" <<'PY'
import sys, yaml
d = yaml.safe_load(open(sys.argv[1]))
for k, v in d["charts"].items(): print(f"  {k:18} {v['chart']:28} {v['version']}")
for k, v in d["refs"].items(): print(f"  {k:18} {v['version']}")
for k, v in d["images"].items(): print(f"  {k:18} {v}")
PY
  use_cluster 2>/dev/null || return 0
  echo "== déployé"
  kubectl get applications.argoproj.io -n argocd -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.sync.revision}{"\n"}{end}' 2>/dev/null | awk '{printf "  %-24s %s\n",$1,substr($2,1,10)}'
  kubectl get pods -A -o jsonpath='{range .items[*]}{range .spec.containers[*]}{.image}{"\n"}{end}{end}' 2>/dev/null | sort -u | grep -E 'vllm|llm-d|litellm|istio|kserve' | sed 's/^/  /'
}

usage() {
  cat <<EOF
usage : $0 <commande>
  preflight            outils, session az, quota T4, SKU, providers
  up                   terraform apply (AKS + Argo CD + GitOps), attente de convergence, puis smoke
  status               nœuds, GPU, applications Argo CD, LLMInferenceService
  smoke                tests sans charge (chaîne complète, B5, Prometheus)
  scenario <nom>       change le scénario actif par Git (gitops/scenarios/<nom>.yaml)
  bench <profil>       smoke|sweep|steady|shared-prefix|multi-turn|long-prompt|burst [--target litellm|gateway|direct]
  ui                   port-forwards Grafana, Prometheus, Alertmanager, Argo CD, LiteLLM
  gpu-scale <0-2>      nombre de nœuds GPU (Terraform)
  stop | start         az aks stop / start (avec revérification)
  down [--yes]         destruction complète
  cost                 estimation du coût horaire
  idle [--stop-after M]  inactivité du GPU ; arrête le cluster au-delà de M minutes
  snapshot-metrics [h] sauvegarde l'historique des règles lab:* (avant down)
  versions             versions épinglées et déployées
  kind-up | kind-down  cluster kind local (KIND_DISABLE=a,b pour alléger ; SCENARIO=kind-mock)
EOF
}

main() {
  local c="${1:-help}"; shift || true
  case "$c" in
    preflight) cmd_preflight "$@" ;;
    up) cmd_up "$@" ;;
    status) cmd_status "$@" ;;
    smoke) cmd_smoke "$@" ;;
    scenario) cmd_scenario "$@" ;;
    bench) cmd_bench "$@" ;;
    ui) cmd_ui "$@" ;;
    gpu-scale) cmd_gpu_scale "$@" ;;
    stop) cmd_stop "$@" ;;
    start) cmd_start "$@" ;;
    down) cmd_down "$@" ;;
    cost) cmd_cost "$@" ;;
    idle) cmd_idle "$@" ;;
    snapshot-metrics) cmd_snapshot_metrics "$@" ;;
    versions) cmd_versions "$@" ;;
    kind-up) cmd_kind_up "$@" ;;
    kind-down) cmd_kind_down "$@" ;;
    help|-h|--help) usage ;;
    *) usage; exit 1 ;;
  esac
}
main "$@"
