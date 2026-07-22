#!/usr/bin/env bash
set -euo pipefail

python3 scripts/verify-release-compliance.py

REPOSITORY_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
CHART_PATH="$REPOSITORY_ROOT/infra/helm/ai-native-content-agency"
IMAGE_TAG=${IMAGE_TAG:-ai-native-content-agency:production-readiness-local}
HOST_PORT=${HOST_PORT:-18080}
CONTAINER_BUILDER=${CONTAINER_BUILDER:-auto}
AUTH_KEY=${AUTH_KEY:-local-production-verification-key-2026}
VIEWER_KEY=${VIEWER_KEY:-local-viewer-verification-key-2026}
IDENTITY_JSON=$(AUTH_KEY="$AUTH_KEY" VIEWER_KEY="$VIEWER_KEY" python3 -c 'import json, os; print(json.dumps([
    {"tenant_id":"local-verification","subject_id":"package-admin","role":"admin","key_id":"package-admin-v1","api_key":os.environ["AUTH_KEY"],"active":True,"entitlements":["theme:premium"]},
    {"tenant_id":"local-verification","subject_id":"package-viewer","role":"viewer","key_id":"package-viewer-v1","api_key":os.environ["VIEWER_KEY"],"active":True},
]))')
HELM_BIN=${HELM_BIN:-helm}
PYTHON_BIN=${PYTHON_BIN:-python3}
TMP_DIR=$(mktemp -d)
RUNTIME_KIND=""
RUNTIME_ID=""
RUNTIME_PID=""

log() {
  printf '[production-verify] %s\n' "$*"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'required command is missing: %s\n' "$1" >&2
    exit 2
  fi
}

cleanup() {
  if [ -n "$RUNTIME_PID" ]; then
    kill "$RUNTIME_PID" >/dev/null 2>&1 || true
    wait "$RUNTIME_PID" >/dev/null 2>&1 || true
  fi
  if [ "$RUNTIME_KIND" = "docker" ] && [ -n "$RUNTIME_ID" ]; then
    docker rm -f "$RUNTIME_ID" >/dev/null 2>&1 || true
  fi
  if [ "$RUNTIME_KIND" = "buildah" ] && [ -n "$RUNTIME_ID" ]; then
    buildah --root "$TMP_DIR/buildah-root" --runroot "$TMP_DIR/buildah-runroot" \
      --storage-driver vfs rm "$RUNTIME_ID" >/dev/null 2>&1 || true
  fi
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

require_command curl
require_command "$PYTHON_BIN"
require_command "$HELM_BIN"

log "validating Helm chart with $($HELM_BIN version --short)"
export XDG_CACHE_HOME="$TMP_DIR/xdg/cache"
export XDG_CONFIG_HOME="$TMP_DIR/xdg/config"
export XDG_DATA_HOME="$TMP_DIR/xdg/data"
mkdir -p "$XDG_CACHE_HOME" "$XDG_CONFIG_HOME" "$XDG_DATA_HOME"
"$HELM_BIN" lint "$CHART_PATH"
"$PYTHON_BIN" "$REPOSITORY_ROOT/scripts/verify-operability.py"
"$HELM_BIN" template agency "$CHART_PATH" > "$TMP_DIR/rendered.yaml"
if grep -q 'kind: PrometheusRule' "$TMP_DIR/rendered.yaml"; then
  printf 'default render unexpectedly contains PrometheusRule\n' >&2
  exit 3
fi
"$HELM_BIN" template agency "$CHART_PATH" \
  --set observability.prometheusRule.enabled=true > "$TMP_DIR/alerts.yaml"
grep -q 'kind: PrometheusRule' "$TMP_DIR/alerts.yaml"
grep -q 'alert: AgencyApiAvailabilityFastBurn' "$TMP_DIR/alerts.yaml"
grep -q 'alert: AgencyBackupStale' "$TMP_DIR/alerts.yaml"
grep -q 'alert: AgencyBackupSignalMissing' "$TMP_DIR/alerts.yaml"
printf 'operability_contract=pass\n'
printf 'prometheus_rule_render=pass\n'
grep -q 'path: /healthz' "$TMP_DIR/rendered.yaml"
grep -q 'path: /readyz' "$TMP_DIR/rendered.yaml"
grep -q 'prometheus.io/scrape' "$TMP_DIR/rendered.yaml"
grep -q 'containerPort: 8080' "$TMP_DIR/rendered.yaml"
grep -q 'name: AGENCY_IDENTITY_CREDENTIALS_JSON' "$TMP_DIR/rendered.yaml"
grep -q 'name: AGENCY_LOGIN_SOURCE_MAX_FAILURES' "$TMP_DIR/rendered.yaml"
grep -q 'name: FORWARDED_ALLOW_IPS' "$TMP_DIR/rendered.yaml"
grep -q 'name: AGENCY_MEMORY_DB' "$TMP_DIR/rendered.yaml"
if grep -q 'name: AGENCY_DATABASE_URL' "$TMP_DIR/rendered.yaml"; then
  printf 'SQLite render unexpectedly contains PostgreSQL URL configuration\n' >&2
  exit 3
fi

"$HELM_BIN" template agency "$CHART_PATH" \
  --set runtime.storage.backend=postgresql \
  --set runtime.storage.postgresql.existingSecret=agency-postgresql \
  --set replicaCount=2 \
  --set persistence.enabled=false \
  --set podDisruptionBudget.enabled=true > "$TMP_DIR/postgresql.yaml"
grep -q 'replicas: 2' "$TMP_DIR/postgresql.yaml"
grep -q 'type: RollingUpdate' "$TMP_DIR/postgresql.yaml"
grep -q 'name: AGENCY_DATABASE_URL' "$TMP_DIR/postgresql.yaml"
grep -q 'name: AGENCY_DATABASE_POOL_MIN_SIZE' "$TMP_DIR/postgresql.yaml"
grep -q 'name: AGENCY_DATABASE_POOL_MAX_SIZE' "$TMP_DIR/postgresql.yaml"
grep -q 'name: AGENCY_DATABASE_CONNECT_TIMEOUT_SECONDS' "$TMP_DIR/postgresql.yaml"
grep -q 'name: AGENCY_POSTGRES_SCHEMA_MODE' "$TMP_DIR/postgresql.yaml"
grep -A1 'name: AGENCY_POSTGRES_SCHEMA_MODE' "$TMP_DIR/postgresql.yaml" | grep -q 'value: "validate"'
if grep -q 'name: AGENCY_MEMORY_DB' "$TMP_DIR/postgresql.yaml"; then
  printf 'PostgreSQL render unexpectedly contains SQLite configuration\n' >&2
  exit 3
fi
if grep -q 'kind: PersistentVolumeClaim' "$TMP_DIR/postgresql.yaml"; then
  printf 'PostgreSQL render unexpectedly contains a runtime PVC\n' >&2
  exit 3
fi

"$HELM_BIN" template agency "$CHART_PATH" \
  --set-string runtime.auth.tenantApiKeysKey='' > "$TMP_DIR/identity-only.yaml"
if grep -q 'name: AGENCY_TENANT_API_KEYS_JSON' "$TMP_DIR/identity-only.yaml"; then
  printf 'identity-only render unexpectedly retained legacy tenant credentials\n' >&2
  exit 3
fi
grep -q 'name: AGENCY_IDENTITY_CREDENTIALS_JSON' "$TMP_DIR/identity-only.yaml"

if "$HELM_BIN" template agency "$CHART_PATH" \
  --set-string runtime.auth.identityCredentialsKey='' >/dev/null 2>&1; then
  printf 'Helm identity requirement guard did not fail\n' >&2
  exit 3
fi
if "$HELM_BIN" template agency "$CHART_PATH" \
  --set runtime.auth.loginMaxFailures=5 \
  --set runtime.auth.loginSourceMaxFailures=4 >/dev/null 2>&1; then
  printf 'Helm source rate-limit guard did not fail\n' >&2
  exit 3
fi
if "$HELM_BIN" template agency "$CHART_PATH" \
  --set runtime.storage.backend=sqlite \
  --set replicaCount=2 >/dev/null 2>&1; then
  printf 'Helm SQLite replica guard did not fail\n' >&2
  exit 3
fi
if "$HELM_BIN" template agency "$CHART_PATH" \
  --set runtime.storage.backend=postgresql >/dev/null 2>&1; then
  printf 'Helm PostgreSQL Secret guard did not fail\n' >&2
  exit 3
fi
if "$HELM_BIN" template agency "$CHART_PATH" \
  --set runtime.storage.backend=postgresql \
  --set runtime.storage.postgresql.existingSecret=agency-postgresql \
  --set runtime.storage.postgresql.schemaMode=initialize >/dev/null 2>&1; then
  printf 'Helm PostgreSQL runtime schema-mode guard did not fail\n' >&2
  exit 3
fi
if "$HELM_BIN" template agency "$CHART_PATH" \
  --set runtime.storage.backend=invalid >/dev/null 2>&1; then
  printf 'Helm storage backend guard did not fail\n' >&2
  exit 3
fi

build_with_docker() {
  require_command docker
  docker info >/dev/null
  docker build --pull --tag "$IMAGE_TAG" "$REPOSITORY_ROOT"
  RUNTIME_KIND=docker
  RUNTIME_ID=$(docker run -d --read-only --tmpfs /tmp:rw,noexec,nosuid,size=32m \
    -e "AGENCY_MEMORY_DB=/tmp/runtime.sqlite3" \
    -e "AGENCY_IDENTITY_CREDENTIALS_JSON=$IDENTITY_JSON" \
    -e "AGENCY_LOGIN_MAX_FAILURES=3" \
    -e "AGENCY_LOGIN_SOURCE_MAX_FAILURES=10" \
    -e "AGENCY_LOGIN_WINDOW_SECONDS=60" \
    -e "AGENCY_SESSION_COOKIE_SECURE=false" \
    -e "AGENCY_SESSION_TTL_SECONDS=600" \
    -p "127.0.0.1:${HOST_PORT}:8080" "$IMAGE_TAG")
}

build_with_buildah() {
  require_command buildah
  mkdir -p "$TMP_DIR/buildah-root" "$TMP_DIR/buildah-runroot"
  export BUILDAH_ISOLATION=chroot
  buildah --root "$TMP_DIR/buildah-root" --runroot "$TMP_DIR/buildah-runroot" \
    --storage-driver vfs bud --isolation chroot --format docker --layers=false \
    --tag "$IMAGE_TAG" "$REPOSITORY_ROOT"
  RUNTIME_KIND=buildah
  RUNTIME_ID=agency-production-readiness-smoke
  buildah --root "$TMP_DIR/buildah-root" --runroot "$TMP_DIR/buildah-runroot" \
    --storage-driver vfs from --name "$RUNTIME_ID" "$IMAGE_TAG" >/dev/null
  buildah --root "$TMP_DIR/buildah-root" --runroot "$TMP_DIR/buildah-runroot" \
    --storage-driver vfs config --env "PORT=$HOST_PORT" \
    --env "AGENCY_MEMORY_DB=/tmp/runtime.sqlite3" \
    --env "AGENCY_IDENTITY_CREDENTIALS_JSON=$IDENTITY_JSON" \
    --env "AGENCY_LOGIN_MAX_FAILURES=3" \
    --env "AGENCY_LOGIN_SOURCE_MAX_FAILURES=10" \
    --env "AGENCY_LOGIN_WINDOW_SECONDS=60" \
    --env "AGENCY_SESSION_COOKIE_SECURE=false" \
    --env "AGENCY_SESSION_TTL_SECONDS=600" "$RUNTIME_ID"
  buildah --root "$TMP_DIR/buildah-root" --runroot "$TMP_DIR/buildah-runroot" \
    --storage-driver vfs run --isolation chroot "$RUNTIME_ID" agency-api \
    > "$TMP_DIR/runtime.log" 2>&1 &
  RUNTIME_PID=$!
}

case "$CONTAINER_BUILDER" in
  docker)
    log "building and running with Docker"
    build_with_docker
    ;;
  buildah)
    log "building and running with Buildah vfs/chroot"
    build_with_buildah
    ;;
  auto)
    if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
      log "attempting Docker build"
      if build_with_docker; then
        :
      elif command -v buildah >/dev/null 2>&1; then
        log "Docker build failed; retrying with Buildah vfs/chroot"
        build_with_buildah
      else
        printf 'Docker build failed and Buildah is unavailable.\n' >&2
        exit 3
      fi
    else
      log "Docker daemon unavailable; using Buildah vfs/chroot"
      build_with_buildah
    fi
    ;;
  *)
    printf 'unsupported CONTAINER_BUILDER: %s\n' "$CONTAINER_BUILDER" >&2
    exit 2
    ;;
esac

ready=0
for _ in $(seq 1 45); do
  if curl -fsS --max-time 2 "http://127.0.0.1:${HOST_PORT}/healthz" \
    > "$TMP_DIR/health.json" 2>/dev/null; then
    ready=1
    break
  fi
  if [ -n "$RUNTIME_PID" ] && ! kill -0 "$RUNTIME_PID" 2>/dev/null; then
    break
  fi
  sleep 1
done

if [ "$ready" -ne 1 ]; then
  [ -f "$TMP_DIR/runtime.log" ] && cat "$TMP_DIR/runtime.log" >&2
  printf 'packaged runtime did not become healthy\n' >&2
  exit 4
fi

curl -fsS "http://127.0.0.1:${HOST_PORT}/readyz" > "$TMP_DIR/ready.json"
curl -fsS "http://127.0.0.1:${HOST_PORT}/" > "$TMP_DIR/index.html"
set +e
viewer_create_status=$(curl -sS -o "$TMP_DIR/viewer-denied.json" -w '%{http_code}'   -H 'Content-Type: application/json'   -H "Authorization: Bearer $VIEWER_KEY"   -H 'X-Request-ID: package-viewer-denied-0001'   -H 'Idempotency-Key: package-viewer-create-0001'   -d '{"title":"Viewer must not create","objective":"Verify least privilege","audience":"reviewers","platforms":["x"],"budget_cents":0,"campaign_goal":"verification"}'   "http://127.0.0.1:${HOST_PORT}/api/v1/runs")
set -e
[ "$viewer_create_status" = "403" ]
curl -fsS \
  -H "Authorization: Bearer $VIEWER_KEY" \
  -H 'X-Request-ID: package-providers-list-0001' \
  "http://127.0.0.1:${HOST_PORT}/api/v1/providers" \
  > "$TMP_DIR/providers.json"
curl -fsS \
  -H "Authorization: Bearer $VIEWER_KEY" \
  -H 'X-Request-ID: package-integrations-list-0001' \
  "http://127.0.0.1:${HOST_PORT}/api/v1/integrations" \
  > "$TMP_DIR/integrations.json"
curl -fsS \
  -H "Authorization: Bearer $VIEWER_KEY" \
  -H 'X-Request-ID: package-integrations-detail-0001' \
  "http://127.0.0.1:${HOST_PORT}/api/v1/integrations/video-use" \
  > "$TMP_DIR/integration-detail.json"
curl -fsS "http://127.0.0.1:${HOST_PORT}/openapi.json" > "$TMP_DIR/openapi.json"
set +e
integration_execute_status=$(curl -sS -o "$TMP_DIR/integration-execute-denied.json" -w '%{http_code}' \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $VIEWER_KEY" \
  -H 'X-Request-ID: package-integration-execute-denied-0001' \
  -d '{"operation":"render_video"}' \
  "http://127.0.0.1:${HOST_PORT}/api/v1/integrations/video-use/execute")
set -e
case "$integration_execute_status" in
  404|405) ;;
  *) printf 'integration execution route returned unsafe status: %s\n' "$integration_execute_status" >&2; exit 4 ;;
esac
python3 - "$TMP_DIR/providers.json" "$TMP_DIR/integrations.json" "$TMP_DIR/integration-detail.json" \
  "$TMP_DIR/openapi.json" "$TMP_DIR/integration-execute-denied.json" <<'PYINTEGRATION'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    providers_payload = json.load(handle)
with open(sys.argv[2], encoding="utf-8") as handle:
    listing = json.load(handle)
with open(sys.argv[3], encoding="utf-8") as handle:
    detail = json.load(handle)
with open(sys.argv[4], encoding="utf-8") as handle:
    openapi = json.load(handle)
with open(sys.argv[5], encoding="utf-8") as handle:
    denied = json.load(handle)

assert providers_payload["tenant_id"] == "local-verification"
providers = providers_payload["providers"]
assert [item["provider_id"] for item in providers] == [
    "openai", "anthropic", "deepseek", "moonshot", "llama"
]
assert all(item["configured"] is False for item in providers)
assert all(item["credential_location"] == "server_environment" for item in providers)
assert "api_key" not in json.dumps(providers_payload).lower()
assert "secret" not in json.dumps(providers_payload).lower()
provider_paths = {
    path: methods
    for path, methods in openapi["paths"].items()
    if path.startswith("/api/v1/providers")
}
assert provider_paths == {"/api/v1/providers": openapi["paths"]["/api/v1/providers"]}
assert set(provider_paths["/api/v1/providers"]) == {"get"}

assert listing["tenant_id"] == "local-verification"
assert len(listing["integrations"]) == 1
integration = listing["integrations"][0]
assert integration["integration_id"] == "video-use"
assert integration["upstream_commit"] == "92c2b34e44c205cbc2acae7f6ca7c1c219d5dd66"
assert integration["review_status"] == "reviewed_disabled"
assert integration["activation_allowed"] is False
assert integration["execution_available"] is False
assert integration["external_effects_enabled"] is False
assert integration["required_binaries"] == ["ffmpeg", "ffprobe"]
assert integration["optional_binaries"] == ["yt-dlp"]
assert detail == {"tenant_id": "local-verification", "integration": integration}
paths = {
    path: methods
    for path, methods in openapi["paths"].items()
    if path.startswith("/api/v1/integrations")
}
assert set(paths) == {
    "/api/v1/integrations",
    "/api/v1/integrations/{integration_id}",
}
assert all(set(methods) == {"get"} for methods in paths.values())
assert denied["code"] in {"resource_not_found", "method_not_allowed"}
assert denied["detail"] in {"resource not found", "method not allowed"}
print("provider_registry=pass")
print("provider_secrets_absent=pass")
print("integration_review_manifest=pass")
print("integration_read_only_api=pass")
print("integration_execution_disabled=pass")
PYINTEGRATION
curl -fsS -c "$TMP_DIR/cookies.txt" -D "$TMP_DIR/session.headers" \
  -H 'Content-Type: application/json' \
  -H 'X-Request-ID: package-session-0001' \
  -d "{\"api_key\":\"$AUTH_KEY\"}" \
  "http://127.0.0.1:${HOST_PORT}/api/v1/sessions" > "$TMP_DIR/session.json"
INITIAL_CSRF=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["csrf_token"])' "$TMP_DIR/session.json")
curl -fsS -b "$TMP_DIR/cookies.txt" \
  "http://127.0.0.1:${HOST_PORT}/api/v1/sessions/current" > "$TMP_DIR/resumed-session.json"
CSRF_TOKEN=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["csrf_token"])' "$TMP_DIR/resumed-session.json")
[ "$INITIAL_CSRF" != "$CSRF_TOKEN" ]
curl -fsS -b "$TMP_DIR/cookies.txt" -D "$TMP_DIR/run.headers" \
  -H 'Content-Type: application/json' \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H 'Idempotency-Key: package-create-command-0001' \
  -H 'X-Request-ID: package-create-0001' \
  -d '{"title":"Packaged runtime verification","objective":"Verify the production browser session package","audience":"production reviewers","platforms":["x","instagram"],"budget_cents":0,"campaign_goal":"verification"}' \
  "http://127.0.0.1:${HOST_PORT}/api/v1/runs" > "$TMP_DIR/run.json"
RUN_ID=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["run_id"])' "$TMP_DIR/run.json")
curl -fsS -b "$TMP_DIR/cookies.txt" -D "$TMP_DIR/approval.headers" \
  -H 'Content-Type: application/json' \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H 'Idempotency-Key: package-approve-command-0001' \
  -H 'X-Request-ID: package-approve-0001' \
  -d '{"reviewer":"package-verifier","note":"Verified packaged sandbox release through browser session"}' \
  "http://127.0.0.1:${HOST_PORT}/api/v1/runs/${RUN_ID}/greenlight/approve" \
  > "$TMP_DIR/approved.json"
curl -fsS -b "$TMP_DIR/cookies.txt" \
  "http://127.0.0.1:${HOST_PORT}/api/v1/audit-events" > "$TMP_DIR/audit.json"
curl -fsS "http://127.0.0.1:${HOST_PORT}/metrics" > "$TMP_DIR/metrics.txt"
curl -fsS -b "$TMP_DIR/cookies.txt" -D "$TMP_DIR/revoke.headers" \
  -X DELETE -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H 'X-Request-ID: package-session-revoke-0001' \
  "http://127.0.0.1:${HOST_PORT}/api/v1/sessions/current" > "$TMP_DIR/revoked.json"
set +e
post_revoke_status=$(curl -sS -o "$TMP_DIR/post-revoke.json" -w '%{http_code}' \
  -b "$TMP_DIR/cookies.txt" "http://127.0.0.1:${HOST_PORT}/api/v1/me")
set -e

python3 - "$TMP_DIR/health.json" "$TMP_DIR/ready.json" "$TMP_DIR/session.json" \
  "$TMP_DIR/resumed-session.json" "$TMP_DIR/run.json" "$TMP_DIR/approved.json" "$TMP_DIR/audit.json" \
  "$TMP_DIR/metrics.txt" "$TMP_DIR/session.headers" "$TMP_DIR/run.headers" \
  "$TMP_DIR/approval.headers" "$TMP_DIR/revoked.json" "$post_revoke_status"   "$TMP_DIR/viewer-denied.json" "$viewer_create_status" <<'PYCHECK'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    health = json.load(handle)
with open(sys.argv[2], encoding="utf-8") as handle:
    ready = json.load(handle)
with open(sys.argv[3], encoding="utf-8") as handle:
    session = json.load(handle)
with open(sys.argv[4], encoding="utf-8") as handle:
    resumed_session = json.load(handle)
with open(sys.argv[5], encoding="utf-8") as handle:
    run = json.load(handle)
with open(sys.argv[6], encoding="utf-8") as handle:
    approved = json.load(handle)
with open(sys.argv[7], encoding="utf-8") as handle:
    audit = json.load(handle)
with open(sys.argv[8], encoding="utf-8") as handle:
    metrics = handle.read()
with open(sys.argv[9], encoding="utf-8") as handle:
    session_headers = handle.read().lower()
with open(sys.argv[10], encoding="utf-8") as handle:
    run_headers = handle.read().lower()
with open(sys.argv[11], encoding="utf-8") as handle:
    approval_headers = handle.read().lower()
with open(sys.argv[12], encoding="utf-8") as handle:
    revoked = json.load(handle)
post_revoke_status = sys.argv[13]
with open(sys.argv[14], encoding="utf-8") as handle:
    viewer_denied = json.load(handle)
viewer_create_status = sys.argv[15]

assert health == {
    "status": "ok",
    "version": "0.7.0",
    "runtime_mode": "deterministic_sandbox",
    "external_side_effects_enabled": False,
    "auth_configured": True,
    "individual_identity_configured": True,
}
assert ready["status"] == "ready"
assert ready["auth_configured"] is True
assert ready["individual_identity_configured"] is True
assert "credential_count" not in ready
assert ready["login_rate_limit"] == {
    "credential_max_failures": 3,
    "source_max_failures": 10,
    "window_seconds": 60,
}
assert viewer_create_status == "403"
assert viewer_denied == {
    "code": "authorization_denied",
    "detail": "request not permitted",
    "request_id": "package-viewer-denied-0001",
}
assert "runs:create" not in repr(viewer_denied)
assert session["tenant_id"] == "local-verification"
assert session["subject_id"] == "package-admin"
assert session["role"] == "admin"
assert session["key_id"] == "package-admin-v1"
assert session["entitlements"] == ["theme:premium"]
assert session["csrf_token"]
assert resumed_session["tenant_id"] == "local-verification"
assert resumed_session["subject_id"] == "package-admin"
assert resumed_session["role"] == "admin"
assert resumed_session["key_id"] == "package-admin-v1"
assert resumed_session["entitlements"] == ["theme:premium"]
assert resumed_session["csrf_token"]
assert resumed_session["csrf_token"] != session["csrf_token"]
assert "httponly" in session_headers
assert "samesite=strict" in session_headers
assert run["tenant_id"] == "local-verification"
assert run["status"] == "awaiting_greenlight"
assert run["agent_states"]["publisher"]["status"] == "waiting_greenlight"
assert [artifact["kind"] for artifact in run["artifacts"]] == [
    "mission_charter",
    "research_dossier",
    "channel_strategy",
    "growth_forecast",
    "copy_deck",
    "media_plan",
    "risk_report",
]
assert approved["status"] == "completed"
package = next(item for item in approved["artifacts"] if item["kind"] == "campaign_package")
assert package["payload"]["publication_performed"] is False
assert [item["action"] for item in audit["events"]] == [
    "authorization.denied",
    "session.created",
    "run.created",
    "greenlight.approved",
]
assert [item["request_id"] for item in audit["events"]] == [
    "package-viewer-denied-0001",
    "package-session-0001",
    "package-create-0001",
    "package-approve-0001",
]
assert [item["actor"] for item in audit["events"]] == [
    "api-key:package-viewer",
    "api-key:package-admin",
    "browser-session:package-admin",
    "browser-session:package-admin",
]
denial = audit["events"][0]
assert denial["payload"] == {
    "auth_method": "bearer",
    "reason": "authorization",
    "role": "viewer",
}
assert "agency_runs_started_total 1" in metrics
assert 'agency_greenlight_decisions_total{decision="approved"} 1' in metrics
assert 'agency_browser_sessions_total{action="created"} 1' in metrics
assert 'agency_authentication_attempts_total{outcome="succeeded"} 5' in metrics
assert "x-request-id: package-session-0001" in session_headers
assert "x-request-id: package-create-0001" in run_headers
assert "x-request-id: package-approve-0001" in approval_headers
assert revoked == {"status": "revoked"}
assert post_revoke_status == "401"
print("health=pass")
print("readiness=pass")
print("spa=pass")
print("individual_identity_rbac=pass")
print("http_only_session=pass")
print("csrf_rotation=pass")
print("csrf_protection=pass")
print("request_correlation=pass")
print("api_vertical_slice=pass")
print("publisher_gate=pass")
print("sandbox_package=pass")
print("durable_audit=pass")
print("prometheus_metrics=pass")
print("session_revocation=pass")
print("external_side_effects_enabled=false")
PYCHECK

if [ -f "$TMP_DIR/runtime.log" ] && { grep -F "$AUTH_KEY" "$TMP_DIR/runtime.log" >/dev/null || grep -F "$VIEWER_KEY" "$TMP_DIR/runtime.log" >/dev/null; }; then
  printf 'runtime logs leaked the bearer credential\n' >&2
  exit 5
fi

log "production package verification passed with ${RUNTIME_KIND}"
