#!/usr/bin/env bash
# Validations statiques (gratuites) : helm template + kubeconform pour chaque composant et chaque environnement,
# promtool sur les règles, terraform validate, shellcheck.
# shellcheck disable=SC2015
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="$HOME/.local/bin:$PATH"
cd "$ROOT"
SCHEMAS=(-schema-location default -schema-location 'https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json')
fail=0
ok()  { printf '  \033[32mOK\033[0m   %s\n' "$*"; }
ko()  { printf '  \033[31mFAIL\033[0m %s\n' "$*"; fail=1; }

echo "== composants Helm / chemins (env: kind azure)"
python3 - >/tmp/components.tsv <<'PY'
import yaml
v = yaml.safe_load(open("gitops/root/values.yaml"))
ver = yaml.safe_load(open("gitops/root/versions.yaml"))["charts"]
for c in v["components"]:
    if c["type"] == "helm":
        k = ver[c["chartKey"]]
        print("\t".join(["helm", c["name"], k["repo"], k["chart"], k["version"], c["valuesDir"], ",".join(c.get("envs", ["kind", "azure"])), c["namespace"]]))
    elif c["type"] == "chart-scenario":
        print("\t".join(["chart", c["name"], c["path"], "-", "-", "-", ",".join(c.get("envs", ["kind", "azure"])), c["namespace"]]))
    else:
        print("\t".join(["path", c["name"], c["path"], "-", "-", "-", ",".join(c.get("envs", ["kind", "azure"])), c["namespace"]]))
PY
while IFS=$'\t' read -r typ name a b c d envs ns; do
  for env in kind azure; do
    [[ ",$envs," == *",$env,"* ]] || continue
    out="/tmp/static-$name-$env.yaml"
    case "$typ" in
      helm)
        vf=(-f "$d/values.yaml"); [[ -f "$d/values-$env.yaml" ]] && vf+=(-f "$d/values-$env.yaml")
        if [[ "$a" == *.* && "$a" != http* ]]; then ref="oci://$a/$b"; else ref=""; fi
        if [[ -n "$ref" ]]; then helm template "$name" "$ref" --version "$c" -n "$ns" "${vf[@]}" --include-crds >"$out" 2>"$out.err" || { ko "$name/$env : $(head -c 300 "$out.err")"; continue; }
        else helm template "$name" "$b" --repo "$a" --version "$c" -n "$ns" "${vf[@]}" --include-crds >"$out" 2>"$out.err" || { ko "$name/$env : $(head -c 300 "$out.err")"; continue; }
        fi ;;
      chart)
        sc=$([[ $env == kind ]] && echo kind-mock || echo baseline-7b)
        helm template "$name" "$a" -f "gitops/scenarios/$sc.yaml" --set env="$env" >"$out" 2>"$out.err" || { ko "$name/$env : $(head -c 300 "$out.err")"; continue; } ;;
      path)
        if [[ -f "$a/kustomization.yaml" ]]; then kustomize build "$a" >"$out" 2>"$out.err" || { ko "$name/$env : $(head -c 300 "$out.err")"; continue; }
        else cat "$a"/*.yaml >"$out"; fi ;;
    esac
    if kubeconform -strict -skip ClusterPolicy -ignore-missing-schemas "${SCHEMAS[@]}" -summary "$out" >/tmp/kc.txt 2>&1; then ok "$name/$env"; else ko "$name/$env : $(grep -E 'invalid|error|Error' /tmp/kc.txt | head -3)"; fi
  done
done </tmp/components.tsv

echo "== promtool"
python3 - <<'PY'
import yaml, subprocess
docs = [d for d in yaml.safe_load_all(open("/tmp/static-observability-config-azure.yaml")) if d and d.get("kind") == "PrometheusRule"]
for d in docs:
    open(f"/tmp/{d['metadata']['name']}.rules.yml", "w").write(yaml.dump({"groups": d["spec"]["groups"]}))
PY
promtool check rules /tmp/lab-recording.rules.yml /tmp/lab-alerts.rules.yml >/tmp/pt.txt 2>&1 && ok "promtool check rules" || { ko "promtool"; cat /tmp/pt.txt; }
if ls tests/promtool/*.yml >/dev/null 2>&1; then
  promtool test rules tests/promtool/*.yml >/tmp/ptt.txt 2>&1 && ok "promtool test rules" || { ko "promtool test"; cat /tmp/ptt.txt; }
fi

echo "== terraform"
(cd infra/terraform && terraform fmt -check -recursive >/dev/null && terraform validate >/dev/null) && ok "terraform fmt + validate" || ko "terraform"
echo "== shellcheck"
shellcheck lab.sh tests/*.sh && ok shellcheck || ko shellcheck
echo "== gitleaks"
gitleaks detect --no-banner --redact -s . >/dev/null 2>&1 && ok "gitleaks (aucun secret)" || ko "gitleaks"
exit $fail
