#!/usr/bin/env bash
set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"

REPOSITORY_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
K3S_PORT=${K3S_PORT:-16443}
NAMESPACE=${NAMESPACE:-agency-terraform-validation}
IMAGE_REPOSITORY=${IMAGE_REPOSITORY:-ai-native-content-agency}
IMAGE_TAG=${IMAGE_TAG:-terraform-validation}
BASE=$(mktemp -d /tmp/agency-local-infra.XXXXXX)
DATA_DIR="$BASE/k3s-data"
KUBECONFIG_PATH="$BASE/kubeconfig.yaml"
K3S_LOG="$BASE/k3s.log"
TF_ROOT="$BASE/infra/terraform"
TF_DATA_DIR="$BASE/terraform-data"
TF_VARS="$BASE/terraform.tfvars"
TF_PLAN="$BASE/terraform.plan"
k3s_pid=""
terraform_applied=0

log() {
  printf '[local-infra] %s\n' "$*"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'required command is missing: %s\n' "$1" >&2
    exit 2
  fi
}

cleanup() {
  if [ "$terraform_applied" -eq 1 ] && [ -s "$KUBECONFIG_PATH" ]; then
    TF_DATA_DIR="$TF_DATA_DIR" terraform -chdir="$TF_ROOT" destroy \
      -var-file="$TF_VARS" -auto-approve >/tmp/agency-local-infra-destroy.log 2>&1 || true
  fi
  if [ -s "$KUBECONFIG_PATH" ]; then
    kubectl --kubeconfig "$KUBECONFIG_PATH" delete namespace "$NAMESPACE" \
      --wait=false >/dev/null 2>&1 || true
  fi
  if [ -n "$k3s_pid" ]; then
    kill -TERM -- "-$k3s_pid" >/dev/null 2>&1 || kill -TERM "$k3s_pid" >/dev/null 2>&1 || true
    for _ in $(seq 1 30); do
      kill -0 "$k3s_pid" >/dev/null 2>&1 || break
      sleep 0.5
    done
    kill -KILL -- "-$k3s_pid" >/dev/null 2>&1 || true
    wait "$k3s_pid" >/dev/null 2>&1 || true
  fi
  mount | awk -v base="$BASE" '$3 ~ "^"base {print $3}' | sort -r | while read -r target; do
    umount "$target" >/dev/null 2>&1 || true
  done
  rm -rf "$BASE"
}
trap cleanup EXIT

for command in terraform helm kubectl k3s ip ss curl python3; do
  require_command "$command"
done

if ss -lnt | awk '{print $4}' | grep -Eq "(^|:)$K3S_PORT$"; then
  printf 'K3S_PORT is already in use: %s\n' "$K3S_PORT" >&2
  exit 2
fi

NODE_IP=$(ip -4 -o addr show dev eth0 | awk '{split($4,a,"/"); print a[1]}')
if [ -z "$NODE_IP" ]; then
  printf 'unable to resolve a non-loopback IPv4 address for eth0\n' >&2
  exit 2
fi

mkdir -p "$DATA_DIR" "$TF_DATA_DIR"
cp -a "$REPOSITORY_ROOT/infra" "$BASE/infra"
cat > "$TF_VARS" <<VARS
kubeconfig_path                  = "$KUBECONFIG_PATH"
namespace                        = "$NAMESPACE"
create_namespace                 = false
image_repository                 = "$IMAGE_REPOSITORY"
image_tag                        = "$IMAGE_TAG"
replica_count                    = 1
persistence_enabled              = false
runtime_auth_existing_secret     = "ai-native-content-agency-runtime"
runtime_auth_tenant_api_keys_key = "tenant-api-keys.json"
runtime_auth_identity_credentials_key = "identity-credentials.json"
login_max_failures               = 5
login_source_max_failures        = 50
login_window_seconds             = 300
forwarded_allow_ips              = "127.0.0.1"
session_cookie_secure            = false
helm_wait                        = false
helm_timeout_seconds             = 60
VARS

log "starting K3s agentless control plane on 127.0.0.1:$K3S_PORT"
setsid k3s server \
  --disable-agent \
  --data-dir "$DATA_DIR" \
  --write-kubeconfig "$KUBECONFIG_PATH" \
  --write-kubeconfig-mode 600 \
  --bind-address 127.0.0.1 \
  --advertise-address "$NODE_IP" \
  --tls-san 127.0.0.1 \
  --https-listen-port "$K3S_PORT" \
  --token agency-local-verification-token \
  --disable coredns \
  --disable servicelb \
  --disable traefik \
  --disable local-storage \
  --disable metrics-server \
  --disable-network-policy \
  --disable-kube-proxy \
  --disable-helm-controller \
  --egress-selector-mode cluster \
  >"$K3S_LOG" 2>&1 &
k3s_pid=$!

ready=0
for _ in $(seq 1 120); do
  if [ -s "$KUBECONFIG_PATH" ]; then
    sed -i "s#server: https://127.0.0.1:6443#server: https://127.0.0.1:$K3S_PORT#" "$KUBECONFIG_PATH"
    if kubectl --kubeconfig "$KUBECONFIG_PATH" get --raw=/readyz >/dev/null 2>&1; then
      ready=1
      break
    fi
  fi
  if ! kill -0 "$k3s_pid" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if [ "$ready" -ne 1 ]; then
  tail -n 180 "$K3S_LOG" >&2 || true
  printf 'K3s API did not become ready\n' >&2
  exit 3
fi

node_count=$(kubectl --kubeconfig "$KUBECONFIG_PATH" get nodes --no-headers 2>/dev/null | wc -l)
if [ "$node_count" -ne 0 ]; then
  printf 'expected an agentless validation control plane, found %s nodes\n' "$node_count" >&2
  exit 3
fi
log "K3s API ready; agentless node_count=0"

log "creating ephemeral namespace and Secret prerequisite"
kubectl --kubeconfig "$KUBECONFIG_PATH" create namespace "$NAMESPACE" >/dev/null
kubectl --kubeconfig "$KUBECONFIG_PATH" -n "$NAMESPACE" create secret generic \
  ai-native-content-agency-runtime \
  --from-literal='tenant-api-keys.json={"local-validation":"local-kubernetes-verification-key-2026"}' \
  --from-literal='identity-credentials.json=[{"tenant_id":"local-validation","subject_id":"infra-validator","role":"admin","key_id":"infra-v1","api_key":"local-identity-verification-key-2026","active":true}]' \
  >/dev/null

log "validating Terraform and planning Helm release"
terraform -chdir="$TF_ROOT" fmt -check -recursive
TF_DATA_DIR="$TF_DATA_DIR" terraform -chdir="$TF_ROOT" init -backend=false -input=false >/dev/null
TF_DATA_DIR="$TF_DATA_DIR" terraform -chdir="$TF_ROOT" validate >/dev/null
TF_DATA_DIR="$TF_DATA_DIR" terraform -chdir="$TF_ROOT" plan \
  -var-file="$TF_VARS" -out="$TF_PLAN" >/dev/null
TF_DATA_DIR="$TF_DATA_DIR" terraform -chdir="$TF_ROOT" show -json "$TF_PLAN" > "$BASE/plan.json"
python3 - "$BASE/plan.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    plan = json.load(handle)
changes = plan.get("resource_changes", [])
assert any(
    item["address"] == "helm_release.app"
    and item["change"]["actions"] == ["create"]
    for item in changes
)
assert not any(item.get("type") == "kubernetes_secret_v1" for item in changes)
assert not any(
    item["address"] == "kubernetes_namespace_v1.app"
    and item["change"]["actions"] != ["no-op"]
    for item in changes
)
print("terraform_plan=helm_release_create")
print("terraform_secret_values_in_state=false")
PY

log "applying Terraform against the real Kubernetes API"
TF_DATA_DIR="$TF_DATA_DIR" terraform -chdir="$TF_ROOT" apply -auto-approve "$TF_PLAN" >/dev/null
terraform_applied=1

kubectl --kubeconfig "$KUBECONFIG_PATH" -n "$NAMESPACE" get deployment \
  ai-native-content-agency-ai-native-content-agency >/dev/null
kubectl --kubeconfig "$KUBECONFIG_PATH" -n "$NAMESPACE" get service \
  ai-native-content-agency-ai-native-content-agency >/dev/null
kubectl --kubeconfig "$KUBECONFIG_PATH" -n "$NAMESPACE" get secret \
  ai-native-content-agency-runtime >/dev/null

helm template ai-native-content-agency "$BASE/infra/helm/ai-native-content-agency" \
  --namespace "$NAMESPACE" --set persistence.enabled=false \
  | kubectl --kubeconfig "$KUBECONFIG_PATH" apply --dry-run=server -f - >/dev/null

kubectl --kubeconfig "$KUBECONFIG_PATH" -n "$NAMESPACE" get deployment \
  ai-native-content-agency-ai-native-content-agency -o json > "$BASE/deployment.json"
python3 - "$BASE/deployment.json" "$IMAGE_REPOSITORY:$IMAGE_TAG" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    deployment = json.load(handle)
container = deployment["spec"]["template"]["spec"]["containers"][0]
environment = {item["name"]: item for item in container["env"]}
assert container["image"] == sys.argv[2]
assert container["readinessProbe"]["httpGet"]["path"] == "/readyz"
legacy = environment["AGENCY_TENANT_API_KEYS_JSON"]["valueFrom"]["secretKeyRef"]
identity = environment["AGENCY_IDENTITY_CREDENTIALS_JSON"]["valueFrom"]["secretKeyRef"]
assert legacy == {
    "name": "ai-native-content-agency-runtime",
    "key": "tenant-api-keys.json",
    "optional": True,
}
assert identity == {
    "name": "ai-native-content-agency-runtime",
    "key": "identity-credentials.json",
}
assert environment["AGENCY_LOGIN_MAX_FAILURES"]["value"] == "5"
assert environment["AGENCY_LOGIN_SOURCE_MAX_FAILURES"]["value"] == "50"
assert environment["AGENCY_LOGIN_WINDOW_SECONDS"]["value"] == "300"
assert environment["FORWARDED_ALLOW_IPS"]["value"] == "127.0.0.1"
print("identity_rbac_configuration=pass")
PY

log "destroying Terraform-managed release"
TF_DATA_DIR="$TF_DATA_DIR" terraform -chdir="$TF_ROOT" destroy \
  -var-file="$TF_VARS" -auto-approve >/dev/null
terraform_applied=0

state_items=$(TF_DATA_DIR="$TF_DATA_DIR" terraform -chdir="$TF_ROOT" state list 2>/dev/null | wc -l)
[ "$state_items" -eq 0 ]
kubectl --kubeconfig "$KUBECONFIG_PATH" delete namespace "$NAMESPACE" --wait=true >/dev/null

printf 'terraform_version=%s\n' "$(terraform version -json | python3 -c 'import json,sys; print(json.load(sys.stdin)["terraform_version"])')"
printf 'helm_version=%s\n' "$(helm version --short)"
printf 'kubectl_client_version=%s\n' "$(kubectl version --client=true -o json | python3 -c 'import json,sys; print(json.load(sys.stdin)["clientVersion"]["gitVersion"])')"
printf 'k3s_version=%s\n' "$(k3s --version | head -n 1 | awk '{print $3}')"
printf 'kubernetes_api=pass\n'
printf 'helm_server_dry_run=pass\n'
printf 'terraform_plan_apply_destroy=pass\n'
printf 'identity_rbac_configuration=pass\n'
printf 'workload_execution=not_validated_agentless_control_plane\n'
printf 'cleanup=pass\n'
