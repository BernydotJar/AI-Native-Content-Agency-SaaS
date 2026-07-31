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
X_TEST_KEY=local-package-x-consumer-key
X_TEST_SECRET=local-package-x-consumer-secret
INSTAGRAM_TEST_APP_ID=local-package-instagram-app-id
INSTAGRAM_TEST_SECRET=local-package-instagram-app-secret
X_TEST_REDIRECT=http://127.0.0.1:${HOST_PORT}/api/v1/social-channels/x/oauth/callback
INSTAGRAM_TEST_REDIRECT=http://127.0.0.1:${HOST_PORT}/api/v1/social-channels/instagram/oauth/callback
SOCIAL_TEST_ACTIVE_KEY_ID=package-social-v1
SOCIAL_TEST_ENCRYPTION_KEYS_JSON='{"package-social-v1":"AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8"}'
AUDIT_TEST_ACTIVE_KEY_ID=package-audit-v1
AUDIT_TEST_SIGNING_KEYS_JSON='{"package-audit-v1":"AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8"}'
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
MOCK_RUNTIME_ID=""

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
  if [ "$RUNTIME_KIND" = "buildah" ] && [ -n "$MOCK_RUNTIME_ID" ]; then
    buildah --root "$TMP_DIR/buildah-root" --runroot "$TMP_DIR/buildah-runroot" \
      --storage-driver vfs rm "$MOCK_RUNTIME_ID" >/dev/null 2>&1 || true
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
grep -A1 'name: AGENCY_AUTHENTICATED_REQUEST_MAX_PER_PRINCIPAL' "$TMP_DIR/rendered.yaml" | grep -q 'value: "600"'
grep -A1 'name: AGENCY_AUTHENTICATED_REQUEST_MAX_PER_TENANT' "$TMP_DIR/rendered.yaml" | grep -q 'value: "6000"'
grep -A1 'name: AGENCY_AUTHENTICATED_REQUEST_WINDOW_SECONDS' "$TMP_DIR/rendered.yaml" | grep -q 'value: "60"'
grep -q 'name: FORWARDED_ALLOW_IPS' "$TMP_DIR/rendered.yaml"
grep -q 'name: AGENCY_MEMORY_DB' "$TMP_DIR/rendered.yaml"
if grep -q 'name: AGENCY_DATABASE_URL' "$TMP_DIR/rendered.yaml"; then
  printf 'SQLite render unexpectedly contains PostgreSQL URL configuration\n' >&2
  exit 3
fi

if grep -q 'name: AGENCY_X_CONSUMER_KEY\|name: AGENCY_INSTAGRAM_APP_ID' "$TMP_DIR/rendered.yaml"; then
  printf 'default render unexpectedly contains social credentials\n' >&2
  exit 3
fi
if grep -q 'name: AGENCY_PUBLIC_MEDIA_' "$TMP_DIR/rendered.yaml"; then
  printf 'default render unexpectedly contains public media configuration\n' >&2
  exit 3
fi
if grep -q 'name: AGENCY_AUDIT_CHECKPOINT_' "$TMP_DIR/rendered.yaml"; then
  printf 'default render unexpectedly contains audit checkpoint Secret refs\n' >&2
  exit 3
fi
grep -A1 'name: AGENCY_MODEL_EXECUTION_ENABLED' "$TMP_DIR/rendered.yaml" | grep -q 'value: "false"'
grep -A1 'name: AGENCY_MODEL_EFFECT_AUTHORITY_ENABLED' "$TMP_DIR/rendered.yaml" | grep -q 'value: "false"'
if grep -q 'name: OPENAI_API_KEY\|name: ANTHROPIC_API_KEY\|name: DEEPSEEK_API_KEY\|name: MOONSHOT_API_KEY\|name: LLAMA_API_KEY' "$TMP_DIR/rendered.yaml"; then
  printf 'default render unexpectedly contains model provider Secret refs\n' >&2
  exit 3
fi
"$HELM_BIN" template agency "$CHART_PATH" \
  --set-string runtime.auditIntegrity.existingSecret=agency-audit-integrity \
  > "$TMP_DIR/audit-integrity.yaml"
grep -q 'name: AGENCY_AUDIT_CHECKPOINT_SIGNING_KEYS_JSON' "$TMP_DIR/audit-integrity.yaml"
grep -A5 'name: AGENCY_AUDIT_CHECKPOINT_SIGNING_KEYS_JSON' "$TMP_DIR/audit-integrity.yaml" | grep -q 'name: "agency-audit-integrity"'
grep -q 'key: "audit-checkpoint-signing-keys.json"' "$TMP_DIR/audit-integrity.yaml"
grep -q 'name: AGENCY_AUDIT_CHECKPOINT_ACTIVE_KEY_ID' "$TMP_DIR/audit-integrity.yaml"
grep -q 'key: "audit-checkpoint-active-key-id"' "$TMP_DIR/audit-integrity.yaml"
if grep -q 'AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8' "$TMP_DIR/audit-integrity.yaml"; then
  printf 'audit checkpoint render leaked signing key material\n' >&2
  exit 3
fi
if "$HELM_BIN" template agency "$CHART_PATH" \
  --set-string runtime.auditIntegrity.existingSecret=agency-audit-integrity \
  --set-string runtime.auditIntegrity.activeKeyIdKey= >/dev/null 2>&1; then
  printf 'Helm audit checkpoint Secret guard did not fail\n' >&2
  exit 3
fi
printf 'audit_checkpoint_secret_refs=pass\n'
printf 'audit_checkpoint_secret_guard=pass\n'

"$HELM_BIN" template agency "$CHART_PATH" \
  --set runtime.model.executionEnabled=true \
  --set runtime.model.effectAuthorityEnabled=true \
  --set-string runtime.model.selectedProvider=openai \
  --set-string runtime.model.egressAllowedHosts=api.openai.com \
  --set-string runtime.model.existingSecret=agency-model \
  --set-string runtime.model.models.openai=gpt-5.2 \
  > "$TMP_DIR/model.yaml"
grep -q 'name: OPENAI_API_KEY' "$TMP_DIR/model.yaml"
grep -A5 'name: OPENAI_API_KEY' "$TMP_DIR/model.yaml" | grep -q 'name: "agency-model"'
grep -A1 'name: AGENCY_MODEL_EFFECT_AUTHORITY_ENABLED' "$TMP_DIR/model.yaml" | grep -q 'value: "true"'
if "$HELM_BIN" template agency "$CHART_PATH" \
  --set runtime.model.effectAuthorityEnabled=true >/dev/null 2>&1; then
  printf 'Helm model authority dependency guard did not fail\n' >&2
  exit 3
fi
printf 'model_effect_default_disabled=pass\n'
printf 'model_provider_secret_refs=pass\n'
printf 'model_authority_guard=pass\n'
"$HELM_BIN" template agency "$CHART_PATH" \
  --set-string runtime.social.existingSecret=agency-social \
  --set-string runtime.social.x.redirectUri="$X_TEST_REDIRECT" \
  --set-string runtime.social.instagram.redirectUri="$INSTAGRAM_TEST_REDIRECT" \
  > "$TMP_DIR/social.yaml"
grep -q 'name: AGENCY_X_CONSUMER_KEY' "$TMP_DIR/social.yaml"
grep -q 'name: AGENCY_X_CONSUMER_SECRET' "$TMP_DIR/social.yaml"
grep -q 'name: AGENCY_INSTAGRAM_APP_ID' "$TMP_DIR/social.yaml"
grep -q 'name: AGENCY_INSTAGRAM_APP_SECRET' "$TMP_DIR/social.yaml"
grep -q 'name: AGENCY_X_REDIRECT_URI' "$TMP_DIR/social.yaml"
grep -q 'name: AGENCY_INSTAGRAM_REDIRECT_URI' "$TMP_DIR/social.yaml"
if grep -q "$X_TEST_SECRET\|$INSTAGRAM_TEST_SECRET" "$TMP_DIR/social.yaml"; then
  printf 'social render leaked credential values\n' >&2
  exit 3
fi
printf 'social_secret_refs=pass\n'

"$HELM_BIN" template agency "$CHART_PATH" \
  --set-string runtime.publicMedia.baseUrl=https://media.example.test \
  --set-string runtime.publicMedia.existingSecret=agency-public-media \
  > "$TMP_DIR/public-media-keyring.yaml"
grep -q 'name: AGENCY_PUBLIC_MEDIA_BASE_URL' "$TMP_DIR/public-media-keyring.yaml"
grep -q 'name: AGENCY_PUBLIC_MEDIA_SIGNING_KEYS_JSON' "$TMP_DIR/public-media-keyring.yaml"
grep -A5 'name: AGENCY_PUBLIC_MEDIA_SIGNING_KEYS_JSON' "$TMP_DIR/public-media-keyring.yaml" | grep -q 'name: "agency-public-media"'
grep -q 'name: AGENCY_PUBLIC_MEDIA_ACTIVE_SIGNING_KEY_ID' "$TMP_DIR/public-media-keyring.yaml"
if grep -q 'name: AGENCY_PUBLIC_MEDIA_SIGNING_KEY$' "$TMP_DIR/public-media-keyring.yaml"; then
  printf 'keyring render unexpectedly contains legacy signing key\n' >&2
  exit 3
fi
"$HELM_BIN" template agency "$CHART_PATH" \
  --set-string runtime.publicMedia.baseUrl=https://media.example.test \
  --set-string runtime.publicMedia.existingSecret=agency-public-media \
  --set-string runtime.publicMedia.signingKeysJsonKey= \
  --set-string runtime.publicMedia.activeSigningKeyIdKey= \
  --set-string runtime.publicMedia.legacySigningKeyKey=public-media-signing-key \
  > "$TMP_DIR/public-media-legacy.yaml"
grep -q 'name: AGENCY_PUBLIC_MEDIA_SIGNING_KEY' "$TMP_DIR/public-media-legacy.yaml"
if grep -q 'name: AGENCY_PUBLIC_MEDIA_SIGNING_KEYS_JSON' "$TMP_DIR/public-media-legacy.yaml"; then
  printf 'legacy render unexpectedly contains keyring configuration\n' >&2
  exit 3
fi
if "$HELM_BIN" template agency "$CHART_PATH" \
  --set-string runtime.publicMedia.baseUrl=https://media.example.test >/dev/null 2>&1; then
  printf 'Helm public-media Secret guard did not fail\n' >&2
  exit 3
fi
if "$HELM_BIN" template agency "$CHART_PATH" \
  --set-string runtime.publicMedia.baseUrl=https://media.example.test \
  --set-string runtime.publicMedia.existingSecret=agency-public-media \
  --set-string runtime.publicMedia.legacySigningKeyKey=public-media-signing-key >/dev/null 2>&1; then
  printf 'Helm public-media ambiguity guard did not fail\n' >&2
  exit 3
fi
printf 'public_media_default_disabled=pass\n'
printf 'public_media_keyring_secret_refs=pass\n'
printf 'public_media_legacy_migration_guard=pass\n'

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
  --set runtime.auth.authenticatedRequestMaxPerPrincipal=100 \
  --set runtime.auth.authenticatedRequestMaxPerTenant=99 >/dev/null 2>&1; then
  printf 'Helm authenticated request quota dependency guard did not fail\n' >&2
  exit 3
fi
printf 'authenticated_request_quota_render=pass\n'
printf 'authenticated_request_quota_guard=pass\n'

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
    -e "AGENCY_AUDIT_CHECKPOINT_SIGNING_KEYS_JSON=$AUDIT_TEST_SIGNING_KEYS_JSON" \
    -e "AGENCY_AUDIT_CHECKPOINT_ACTIVE_KEY_ID=$AUDIT_TEST_ACTIVE_KEY_ID" \
    -e "AGENCY_SESSION_COOKIE_SECURE=false" \
    -e "AGENCY_SESSION_TTL_SECONDS=600" \
    -e "AGENCY_X_CONSUMER_KEY=$X_TEST_KEY" \
    -e "AGENCY_X_CONSUMER_SECRET=$X_TEST_SECRET" \
    -e "AGENCY_X_REDIRECT_URI=$X_TEST_REDIRECT" \
    -e "AGENCY_INSTAGRAM_APP_ID=$INSTAGRAM_TEST_APP_ID" \
    -e "AGENCY_INSTAGRAM_APP_SECRET=$INSTAGRAM_TEST_SECRET" \
    -e "AGENCY_INSTAGRAM_REDIRECT_URI=$INSTAGRAM_TEST_REDIRECT" \
    -e "AGENCY_SOCIAL_TOKEN_ACTIVE_KEY_ID=$SOCIAL_TEST_ACTIVE_KEY_ID" \
    -e "AGENCY_SOCIAL_PUBLICATION_ENABLED=false" \
    -e "AGENCY_MODEL_EXECUTION_ENABLED=false" \
    -e "AGENCY_MODEL_EFFECT_AUTHORITY_ENABLED=false" \
    -e "AGENCY_SOCIAL_TOKEN_ENCRYPTION_KEYS_JSON=$SOCIAL_TEST_ENCRYPTION_KEYS_JSON" \
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
    --env "AGENCY_AUDIT_CHECKPOINT_SIGNING_KEYS_JSON=$AUDIT_TEST_SIGNING_KEYS_JSON" \
    --env "AGENCY_AUDIT_CHECKPOINT_ACTIVE_KEY_ID=$AUDIT_TEST_ACTIVE_KEY_ID" \
    --env "AGENCY_SESSION_COOKIE_SECURE=false" \
    --env "AGENCY_SESSION_TTL_SECONDS=600" \
    --env "AGENCY_X_CONSUMER_KEY=$X_TEST_KEY" \
    --env "AGENCY_X_CONSUMER_SECRET=$X_TEST_SECRET" \
    --env "AGENCY_X_REDIRECT_URI=$X_TEST_REDIRECT" \
    --env "AGENCY_INSTAGRAM_APP_ID=$INSTAGRAM_TEST_APP_ID" \
    --env "AGENCY_INSTAGRAM_APP_SECRET=$INSTAGRAM_TEST_SECRET" \
    --env "AGENCY_INSTAGRAM_REDIRECT_URI=$INSTAGRAM_TEST_REDIRECT" \
    --env "AGENCY_SOCIAL_TOKEN_ACTIVE_KEY_ID=$SOCIAL_TEST_ACTIVE_KEY_ID" \
    --env "AGENCY_SOCIAL_PUBLICATION_ENABLED=false" \
    --env "AGENCY_MODEL_EXECUTION_ENABLED=false" \
    --env "AGENCY_MODEL_EFFECT_AUTHORITY_ENABLED=false" \
    --env "AGENCY_SOCIAL_TOKEN_ENCRYPTION_KEYS_JSON=$SOCIAL_TEST_ENCRYPTION_KEYS_JSON" "$RUNTIME_ID"
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
curl -fsS \
  -H "Authorization: Bearer $VIEWER_KEY" \
  -H 'X-Request-ID: package-social-channels-0001' \
  "http://127.0.0.1:${HOST_PORT}/api/v1/social-channels" \
  > "$TMP_DIR/social-channels.json"
curl -fsS "http://127.0.0.1:${HOST_PORT}/openapi.json" > "$TMP_DIR/openapi.json"
python3 - "$TMP_DIR/openapi.json" "$REPOSITORY_ROOT/contracts/openapi-v1.json" <<'PYAPICONTRACT'
import hashlib
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    installed = json.load(handle)
with open(sys.argv[2], encoding="utf-8") as handle:
    committed = json.load(handle)

def canonical(document):
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

installed_bytes = canonical(installed).encode("utf-8")
committed_bytes = canonical(committed).encode("utf-8")
assert installed_bytes == committed_bytes
print("installed_api_contract=pass")
print("api_contract_sha256=" + hashlib.sha256(installed_bytes).hexdigest())
PYAPICONTRACT
set +e
social_oauth_bearer_status=$(curl -sS -o "$TMP_DIR/social-oauth-bearer-denied.json" -w '%{http_code}' \
  -X POST -H "Authorization: Bearer $AUTH_KEY" \
  -H 'X-Request-ID: package-social-oauth-bearer-denied-0001' \
  "http://127.0.0.1:${HOST_PORT}/api/v1/social-channels/x/oauth/start")
set -e
[ "$social_oauth_bearer_status" = "400" ]
grep -q '"code":"browser_session_required"' "$TMP_DIR/social-oauth-bearer-denied.json"
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
  "$TMP_DIR/social-channels.json" "$TMP_DIR/openapi.json" "$TMP_DIR/integration-execute-denied.json" <<'PYINTEGRATION'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    providers_payload = json.load(handle)
with open(sys.argv[2], encoding="utf-8") as handle:
    listing = json.load(handle)
with open(sys.argv[3], encoding="utf-8") as handle:
    detail = json.load(handle)
with open(sys.argv[4], encoding="utf-8") as handle:
    social = json.load(handle)
with open(sys.argv[5], encoding="utf-8") as handle:
    openapi = json.load(handle)
with open(sys.argv[6], encoding="utf-8") as handle:
    denied = json.load(handle)

assert providers_payload["tenant_id"] == "local-verification"
assert providers_payload["gateway"] == {
    "execution_enabled": False,
    "selected_provider": "",
    "execution_available": False,
    "durable_outbound_receipt": False,
    "automatic_run_integration": False,
}
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
assert "/api/v1/model-completions" not in openapi["paths"]
assert "/api/v1/providers/execute" not in openapi["paths"]
assert set(openapi["paths"]["/api/v1/runs/{run_id}/model-effects/{station}"]) == {"post"}
assert set(openapi["paths"]["/api/v1/runs/{run_id}/model-effects"]) == {"get"}
assert set(openapi["paths"]["/api/v1/model-effects/{effect_id}/reconcile"]) == {"post"}

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
assert social["tenant_id"] == "local-verification"
channels = social["channels"]
assert [item["channel_id"] for item in channels] == ["x", "instagram"]
assert all(item["configuration_state"] == "ready_for_authentication" for item in channels)
assert all(item["connection_state"] == "not_connected" for item in channels)
assert all(item["oauth_runtime_configured"] is True for item in channels)
assert all(item["oauth_start_available"] is True for item in channels)
assert all(item["publication_runtime_configured"] is True for item in channels)
assert all(item["publication_execution_enabled"] is False for item in channels)
assert all(item["publishing_available"] is False for item in channels)
assert all(item["connected_account"] is None for item in channels)
assert channels[0]["requires_media"] is False
assert channels[1]["requires_media"] is True
serialized_social = json.dumps(social)
for secret in (
    "local-package-x-consumer-key",
    "local-package-x-consumer-secret",
    "local-package-instagram-app-id",
    "local-package-instagram-app-secret",
    "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8",
):
    assert secret not in serialized_social
social_paths = {
    path: methods
    for path, methods in openapi["paths"].items()
    if path.startswith("/api/v1/social-channels")
}
assert set(social_paths) == {
    "/api/v1/social-channels",
    "/api/v1/social-channels/{channel_id}",
    "/api/v1/social-channels/{channel_id}/oauth/start",
    "/api/v1/social-channels/x/oauth/callback",
    "/api/v1/social-channels/instagram/oauth/callback",
    "/api/v1/social-channels/{channel_id}/connection",
}
assert set(social_paths["/api/v1/social-channels"]) == {"get"}
assert set(social_paths["/api/v1/social-channels/{channel_id}"]) == {"get"}
assert set(social_paths["/api/v1/social-channels/{channel_id}/oauth/start"]) == {"post"}
assert set(social_paths["/api/v1/social-channels/{channel_id}/connection"]) == {"delete"}
assert "/api/v1/social-channels/{channel_id}/publish" not in openapi["paths"]
assert set(openapi["paths"]["/api/v1/runs/{run_id}/social-publications/{channel_id}"]) == {"post"}
assert set(openapi["paths"]["/api/v1/runs/{run_id}/social-publications"]) == {"get"}
assert set(openapi["paths"]["/api/v1/social-publications/{intent_id}/reconcile"]) == {"post"}
print("provider_registry=pass")
print("model_gateway_disabled=pass")
print("model_effect_routes_governed=pass")
print("provider_secrets_absent=pass")
print("integration_review_manifest=pass")
print("integration_read_only_api=pass")
print("integration_execution_disabled=pass")
print("social_channel_readiness=pass")
print("social_secrets_absent=pass")
print("social_oauth_routes_governed=pass")
print("social_publication_routes_governed=pass")
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
WRITER_ARTIFACT_ID=$(python3 -c 'import json,sys; data=json.load(open(sys.argv[1])); print(next(item["artifact_id"] for item in data["artifacts"] if item["created_by"] == "writer"))' "$TMP_DIR/run.json")
set +e
MODEL_EFFECT_PAYLOAD=$(python3 - "$WRITER_ARTIFACT_ID" <<'PYMODELREQUEST'
import json
import sys
print(json.dumps({
    "source_artifact_id": sys.argv[1],
    "instruction": "Package default-disabled verification",
    "max_cost_micros": 0,
}, separators=(",", ":")))
PYMODELREQUEST
)
model_effect_disabled_status=$(curl -sS -o "$TMP_DIR/model-effect-disabled.json" -w '%{http_code}' \
  -b "$TMP_DIR/cookies.txt" \
  -H 'Content-Type: application/json' \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H 'Idempotency-Key: package-model-effect-disabled-0001' \
  -H 'X-Request-ID: package-model-effect-disabled-0001' \
  --data-binary "$MODEL_EFFECT_PAYLOAD" \
  "http://127.0.0.1:${HOST_PORT}/api/v1/runs/${RUN_ID}/model-effects/writer")
set -e
[ "$model_effect_disabled_status" = "409" ]
curl -fsS -b "$TMP_DIR/cookies.txt" -D "$TMP_DIR/approval.headers" \
  -H 'Content-Type: application/json' \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H 'Idempotency-Key: package-approve-command-0001' \
  -H 'X-Request-ID: package-approve-0001' \
  -d '{"reviewer":"package-verifier","note":"Verified packaged sandbox release through browser session"}' \
  "http://127.0.0.1:${HOST_PORT}/api/v1/runs/${RUN_ID}/greenlight/approve" \
  > "$TMP_DIR/approved.json"
COPY_ARTIFACT_ID=$(python3 -c 'import json,sys; data=json.load(open(sys.argv[1])); print(next(item["artifact_id"] for item in data["artifacts"] if item["kind"] == "copy_deck"))' "$TMP_DIR/approved.json")
GREENLIGHT_ID=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["greenlight"]["greenlight_id"])' "$TMP_DIR/approved.json")
GREENLIGHT_FENCE=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["greenlight"]["fencing_token"])' "$TMP_DIR/approved.json")
set +e
publication_disabled_status=$(curl -sS -o "$TMP_DIR/publication-disabled.json" -w '%{http_code}' \
  -b "$TMP_DIR/cookies.txt" \
  -H 'Content-Type: application/json' \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H 'Idempotency-Key: package-publication-disabled-0001' \
  -H 'X-Request-ID: package-publication-disabled-0001' \
  -d "{\"artifact_id\":\"$COPY_ARTIFACT_ID\",\"media_artifact_id\":null,\"greenlight_id\":\"$GREENLIGHT_ID\",\"greenlight_fencing_token\":$GREENLIGHT_FENCE}" \
  "http://127.0.0.1:${HOST_PORT}/api/v1/runs/${RUN_ID}/social-publications/x")
set -e
[ "$publication_disabled_status" = "409" ]
curl -fsS -b "$TMP_DIR/cookies.txt" \
  "http://127.0.0.1:${HOST_PORT}/api/v1/audit-events" > "$TMP_DIR/audit.json"
curl -fsS -b "$TMP_DIR/cookies.txt" \
  "http://127.0.0.1:${HOST_PORT}/api/v1/audit-events/integrity" > "$TMP_DIR/audit-checkpoint.json"
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
  "$TMP_DIR/approval.headers" "$TMP_DIR/revoked.json" "$post_revoke_status" \
  "$TMP_DIR/viewer-denied.json" "$viewer_create_status" \
  "$TMP_DIR/publication-disabled.json" "$publication_disabled_status" \
  "$TMP_DIR/model-effect-disabled.json" "$model_effect_disabled_status" \
  "$TMP_DIR/audit-checkpoint.json" <<'PYCHECK'
import base64
import hashlib
import hmac
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
with open(sys.argv[16], encoding="utf-8") as handle:
    publication_disabled = json.load(handle)
publication_disabled_status = sys.argv[17]
with open(sys.argv[18], encoding="utf-8") as handle:
    model_effect_disabled = json.load(handle)
model_effect_disabled_status = sys.argv[19]
with open(sys.argv[20], encoding="utf-8") as handle:
    audit_checkpoint = json.load(handle)

assert health == {
    "status": "ok",
    "version": "0.7.0",
    "runtime_mode": "deterministic_sandbox",
    "external_side_effects_enabled": False,
    "model_effect_authority_enabled": False,
    "auth_configured": True,
    "individual_identity_configured": True,
    "authenticated_request_quota_enabled": True,
    "audit_integrity_chain_enabled": True,
    "audit_checkpoint_signing_configured": True,
}
assert ready["status"] == "ready"
assert ready["auth_configured"] is True
assert ready["individual_identity_configured"] is True
assert ready["model_effect_authority_enabled"] is False
assert "credential_count" not in ready
assert ready["login_rate_limit"] == {
    "credential_max_failures": 3,
    "source_max_failures": 10,
    "window_seconds": 60,
}
assert ready["authenticated_request_quota"] == {
    "principal_max_requests": 600,
    "tenant_max_requests": 6000,
    "window_seconds": 60,
}
assert ready["audit_integrity"] == {
    "chain_enabled": True,
    "checkpoint_signing_configured": True,
    "active_key_id": "package-audit-v1",
}
assert viewer_create_status == "403"
assert publication_disabled_status == "409"
assert publication_disabled["code"] == "social_publication_unavailable"
assert model_effect_disabled_status == "409"
assert model_effect_disabled["code"] == "model_effect_unavailable"
assert model_effect_disabled["detail"] == "model effect authority is disabled"
assert publication_disabled["detail"] == "social publication is disabled"
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
assert "samesite=lax" in session_headers
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
assert audit["events"][0]["previous_hash"] == "0" * 64
for previous, current in zip(audit["events"], audit["events"][1:]):
    assert current["previous_hash"] == previous["event_hash"]
assert audit_checkpoint["schema_version"] == "audit-checkpoint.v1"
assert audit_checkpoint["tenant_id"] == "local-verification"
assert audit_checkpoint["event_count"] == len(audit["events"])
assert audit_checkpoint["head_event_id"] == audit["events"][-1]["event_id"]
assert audit_checkpoint["head_hash"] == audit["events"][-1]["event_hash"]
assert audit_checkpoint["key_id"] == "package-audit-v1"
checkpoint_document = {
    key: audit_checkpoint[key]
    for key in (
        "schema_version",
        "tenant_id",
        "event_count",
        "head_event_id",
        "head_hash",
        "verified_at",
    )
}
canonical = json.dumps(
    checkpoint_document,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
).encode("utf-8")
key = base64.urlsafe_b64decode(
    "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8="
)
expected_signature = base64.urlsafe_b64encode(
    hmac.new(key, canonical, hashlib.sha256).digest()
).rstrip(b"=").decode("ascii")
assert hmac.compare_digest(expected_signature, audit_checkpoint["signature"])
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
assert 'agency_authentication_attempts_total{outcome="succeeded"} 7' in metrics
assert 'agency_authenticated_request_quota_total{outcome="allowed"}' in metrics
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
print("social_publication_default_disabled=pass")
print("model_effect_default_disabled=pass")
print("sandbox_package=pass")
print("durable_audit=pass")
print("audit_chain_checkpoint=pass")
print("prometheus_metrics=pass")
print("authenticated_request_quota_package=pass")
print("session_revocation=pass")
print("external_side_effects_enabled=false")
PYCHECK

async_status=$(curl -sS -o "$TMP_DIR/async-run.json" -D "$TMP_DIR/async-run.headers" -w '%{http_code}' \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $AUTH_KEY" \
  -H 'Prefer: respond-async' \
  -H 'Idempotency-Key: package-async-command-0001' \
  -H 'X-Request-ID: package-async-create-0001' \
  -d '{"title":"Packaged asynchronous runtime","objective":"Verify durable station checkpoints inside the production image","audience":"production reviewers","platforms":["x","instagram"],"budget_cents":0,"campaign_goal":"verification"}' \
  "http://127.0.0.1:${HOST_PORT}/api/v1/runs")
[ "$async_status" = "202" ]
ASYNC_RUN_ID=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["run_id"])' "$TMP_DIR/async-run.json")
for _ in $(seq 1 100); do
  curl -fsS --connect-timeout 2 --max-time 5 \
    -H "Authorization: Bearer $AUTH_KEY" \
    "http://127.0.0.1:${HOST_PORT}/api/v1/runs/${ASYNC_RUN_ID}" > "$TMP_DIR/async-current.json"
  current_status=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "$TMP_DIR/async-current.json")
  if [ "$current_status" = "awaiting_greenlight" ]; then
    break
  fi
  sleep 0.15
done
curl -fsS --connect-timeout 2 --max-time 5 \
  -H "Authorization: Bearer $AUTH_KEY" \
  "http://127.0.0.1:${HOST_PORT}/api/v1/audit-events?limit=100" > "$TMP_DIR/async-audit.json"
python3 - "$TMP_DIR/async-run.json" "$TMP_DIR/async-current.json" "$TMP_DIR/async-run.headers" "$TMP_DIR/async-audit.json" <<'PYASYNC'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    queued = json.load(handle)
with open(sys.argv[2], encoding="utf-8") as handle:
    final = json.load(handle)
with open(sys.argv[3], encoding="utf-8") as handle:
    headers = handle.read().lower()
with open(sys.argv[4], encoding="utf-8") as handle:
    audit = json.load(handle)
assert queued["status"] == "queued"
assert queued["execution"]["fencing_token"] == 0
assert "preference-applied: respond-async" in headers
assert "location: /api/v1/runs/" in headers
assert final["status"] == "awaiting_greenlight"
assert final["execution"]["state"] == "awaiting_greenlight"
assert final["execution"]["fencing_token"] == 14
assert final["execution"]["lease_owner"] == ""
assert len(final["artifacts"]) == 7
checkpoints = [
    item for item in audit["events"]
    if item["resource_id"] == final["run_id"] and item["action"] == "run.checkpointed"
]
assert [item["payload"]["fencing_token"] for item in checkpoints] == list(range(1, 15))
assert all(item["actor"].startswith("system:worker-") for item in checkpoints)
print("async_run_accepted=pass")
print("async_run_durable_checkpoints=pass")
print("async_run_package_greenlight=pass")
PYASYNC

if [ -f "$TMP_DIR/runtime.log" ] && {
  grep -F "$AUTH_KEY" "$TMP_DIR/runtime.log" >/dev/null ||
  grep -F "$VIEWER_KEY" "$TMP_DIR/runtime.log" >/dev/null ||
  grep -F "$X_TEST_SECRET" "$TMP_DIR/runtime.log" >/dev/null ||
  grep -F "$INSTAGRAM_TEST_SECRET" "$TMP_DIR/runtime.log" >/dev/null;
}; then
  printf 'runtime logs leaked a credential\n' >&2
  exit 5
fi

PUBLICATION_FIXTURE="$REPOSITORY_ROOT/scripts/fixtures/verify_social_publication_package.py"
MODEL_EFFECT_FIXTURE="$REPOSITORY_ROOT/scripts/fixtures/verify_model_effect_package.py"
case "$RUNTIME_KIND" in
  docker)
    docker run --rm --read-only --tmpfs /tmp:rw,noexec,nosuid,size=32m \
      --network none -i "$IMAGE_TAG" python - < "$PUBLICATION_FIXTURE"
    docker run --rm --read-only --tmpfs /tmp:rw,noexec,nosuid,size=32m \
      --network none -i "$IMAGE_TAG" python - < "$MODEL_EFFECT_FIXTURE"
    ;;
  buildah)
    MOCK_RUNTIME_ID=agency-production-publication-mock
    buildah --root "$TMP_DIR/buildah-root" --runroot "$TMP_DIR/buildah-runroot" \
      --storage-driver vfs from --name "$MOCK_RUNTIME_ID" "$IMAGE_TAG" >/dev/null
    buildah --root "$TMP_DIR/buildah-root" --runroot "$TMP_DIR/buildah-runroot" \
      --storage-driver vfs run --isolation chroot \
      "$MOCK_RUNTIME_ID" python - < "$PUBLICATION_FIXTURE"
    buildah --root "$TMP_DIR/buildah-root" --runroot "$TMP_DIR/buildah-runroot" \
      --storage-driver vfs run --isolation chroot \
      "$MOCK_RUNTIME_ID" python - < "$MODEL_EFFECT_FIXTURE"
    ;;
  *)
    printf 'unsupported runtime for publication package fixture: %s\n' "$RUNTIME_KIND" >&2
    exit 5
    ;;
esac

log "production package verification passed with ${RUNTIME_KIND}"
