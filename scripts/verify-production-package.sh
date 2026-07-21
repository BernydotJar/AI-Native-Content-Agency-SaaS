#!/usr/bin/env bash
set -euo pipefail

REPOSITORY_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
CHART_PATH="$REPOSITORY_ROOT/infra/helm/ai-native-content-agency"
IMAGE_TAG=${IMAGE_TAG:-ai-native-content-agency:production-readiness-local}
HOST_PORT=${HOST_PORT:-18080}
CONTAINER_BUILDER=${CONTAINER_BUILDER:-auto}
AUTH_KEY=${AUTH_KEY:-local-production-verification-key-2026}
AUTH_JSON=$(AUTH_KEY="$AUTH_KEY" python3 -c 'import json, os; print(json.dumps({"local-verification": os.environ["AUTH_KEY"]}))')
HELM_BIN=${HELM_BIN:-helm}
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
require_command python3
require_command "$HELM_BIN"

log "validating Helm chart with $($HELM_BIN version --short)"
export XDG_CACHE_HOME="$TMP_DIR/xdg/cache"
export XDG_CONFIG_HOME="$TMP_DIR/xdg/config"
export XDG_DATA_HOME="$TMP_DIR/xdg/data"
mkdir -p "$XDG_CACHE_HOME" "$XDG_CONFIG_HOME" "$XDG_DATA_HOME"
"$HELM_BIN" lint "$CHART_PATH"
"$HELM_BIN" template agency "$CHART_PATH" > "$TMP_DIR/rendered.yaml"
grep -q 'path: /healthz' "$TMP_DIR/rendered.yaml"
grep -q 'containerPort: 8080' "$TMP_DIR/rendered.yaml"

build_with_docker() {
  require_command docker
  docker info >/dev/null
  docker build --pull --tag "$IMAGE_TAG" "$REPOSITORY_ROOT"
  RUNTIME_KIND=docker
  RUNTIME_ID=$(docker run -d --read-only --tmpfs /tmp:rw,noexec,nosuid,size=32m \
    -e "AGENCY_MEMORY_DB=/tmp/runtime.sqlite3" \
    -e "AGENCY_TENANT_API_KEYS_JSON=$AUTH_JSON" \
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
    --env "AGENCY_TENANT_API_KEYS_JSON=$AUTH_JSON" "$RUNTIME_ID"
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
curl -fsS -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $AUTH_KEY" \
  -d '{"title":"Packaged runtime verification","objective":"Verify the production package","audience":"production reviewers","platforms":["x","instagram"],"budget_cents":0,"campaign_goal":"verification"}' \
  "http://127.0.0.1:${HOST_PORT}/api/v1/runs" > "$TMP_DIR/run.json"

python3 - "$TMP_DIR/health.json" "$TMP_DIR/ready.json" "$TMP_DIR/run.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    health = json.load(handle)
with open(sys.argv[2], encoding="utf-8") as handle:
    ready = json.load(handle)
with open(sys.argv[3], encoding="utf-8") as handle:
    run = json.load(handle)

assert health == {
    "status": "ok",
    "runtime_mode": "deterministic_sandbox",
    "external_side_effects_enabled": False,
    "auth_configured": True,
}
assert ready["status"] == "ready"
assert ready["auth_configured"] is True
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
print("health=pass")
print("readiness=pass")
print("spa=pass")
print("tenant_auth=pass")
print("api_vertical_slice=pass")
print("publisher_gate=pass")
print("external_side_effects_enabled=false")
PY

log "production package verification passed with ${RUNTIME_KIND}"
