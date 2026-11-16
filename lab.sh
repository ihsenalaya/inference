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
  az aks get-credentials -g "$RG" -n "$AKS" --overwrite-existing --file "${TMPDIR:-/tmp}/kubeconfig-aks-$PREFIX" >/dev/null
  export KUBECONFIG="${TMPDIR:-/tmp}/kubeconfig-aks-$PREFIX"
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
  sleep 3
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
import json, sys
d = json.loads(sys.argv[1])
t = d["choices"][0]["message"]["content"].strip()
# sortie cohérente : non vide, pas dégénérée (un même mot répété plus de 60 % du temps)
w = t.split()
assert len(w) >= 3, "sortie trop courte"
assert max(w.count(x) for x in set(w)) / len(w) < 0.6, "sortie dégénérée"
PY
}

cmd_smoke() {
  use_cluster; PASS=0; FAILN=0
  local alias
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
  [[ -n "$profile" ]] || die "usage : $0 bench <smoke|sweep|steady|shared-prefix|multi-turn|long-prompt|burst> [--target litellm|gateway] [--model alias]"
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
    key="$(litellm_key lab-bench)"; base="http://litellm.gateway.svc:4000"; apipath=""
    model="$alias_name"
  else
    key=""; base="http://inference-gateway-istio.inference.svc.cluster.local"; apipath="/inference/${res_name}"; model="$hf_name"
  fi
  local extra=()
  [[ -n "${RATE:-}" ]] && extra+=(--set "rate=$RATE")
  [[ -n "${DURATION:-}" ]] && extra+=(--set "duration=$DURATION")
  log INFO "bench $profile sur $scen (cible $target, modèle $model)"
  grafana_annotation "bench $profile début | scénario $scen | git $sha | cible $target" '"bench","start"'
  helm template bench "$ROOT/gitops/bench" --set profile="$profile" --set name="$name" --set baseUrl="$base" --set apiPath="$apipath" \
    --set apiKey="$key" --set model="$model" --set tokenizerModel="${hf_name:-$model}" "${extra[@]}" | kubectl apply -f - >/dev/null
  local out; out="$ROOT/results/$(date +%Y-%m-%d)-${scen}-${profile}"; mkdir -p "$out"
  kubectl -n inference wait --for=condition=complete "job/$name" --timeout="${BENCH_TIMEOUT:-3600}s" >/dev/null 2>&1 || \
    kubectl -n inference wait --for=condition=failed "job/$name" --timeout=5s >/dev/null 2>&1 || true
  kubectl -n inference logs "job/$name" >"$out/run.log" 2>&1 || true
  python3 - "$out" <<'PY'
import pathlib, re, sys
out = pathlib.Path(sys.argv[1]); log = (out / "run.log").read_text()
m = re.search(r"===LAB-RESULTS-BEGIN===\n(.*)===LAB-RESULTS-END===", log, re.S)
if m:
    cur = None
    for line in m.group(1).splitlines(keepends=True):
        if line.startswith("=== FILE "):
            cur = out / line[9:].strip(); cur.parent.mkdir(parents=True, exist_ok=True); cur.write_text("")
        elif cur is not None:
            with cur.open("a") as f: f.write(line)
PY
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
  cmd_smoke
}

cmd_down() {
  local yes=false; [[ "${1:-}" == "--yes" ]] && yes=true
  az_ok
  if [[ $yes != true ]]; then
    read -r -p "Détruire TOUT le lab ($RG, AKS, nœuds GPU) ? taper 'oui' : " a; [[ "$a" == oui ]] || die "annulé"
  fi
  tf_vars
  tf destroy -input=false -auto-approve "${TF_VARS[@]}"
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
  bench <profil>       smoke|sweep|steady|shared-prefix|multi-turn|long-prompt|burst [--target litellm|gateway]
  ui                   port-forwards Grafana, Prometheus, Alertmanager, Argo CD, LiteLLM
  gpu-scale <0-2>      nombre de nœuds GPU (Terraform)
  stop | start         az aks stop / start (avec revérification)
  down [--yes]         destruction complète
  cost                 estimation du coût horaire
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
    versions) cmd_versions "$@" ;;
    kind-up) cmd_kind_up "$@" ;;
    kind-down) cmd_kind_down "$@" ;;
    help|-h|--help) usage ;;
    *) usage; exit 1 ;;
  esac
}
main "$@"
