#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${AGENCY_ENV_FILE:-$ROOT_DIR/.env.local}"
STATE_DIR="$ROOT_DIR/.local"
PRODUCT_LOG="$STATE_DIR/product.log"
API_LOG="$STATE_DIR/api.log"
TUNNEL_LOG="$STATE_DIR/cloudflared.log"
TUNNEL_STDOUT="$STATE_DIR/cloudflared.stdout.log"
PUBLIC_URL_FILE="$STATE_DIR/current-public-url"
PRODUCT_PID_FILE="$STATE_DIR/product-launcher.pid"
API_PID_FILE="$STATE_DIR/api.pid"
TUNNEL_PID_FILE="$STATE_DIR/cloudflared.pid"
RUNTIME_ENV_HASH_FILE="$STATE_DIR/runtime-env.sha256"
LOCK_FILE="$STATE_DIR/workspace-up.lock"
SOCIAL_BACKUP_DIR="$STATE_DIR/social-connection-backups"
SOCIAL_BACKUP_STATE_FILE="$STATE_DIR/social-connection-state.sha256"
SOCIAL_BACKUP_MANIFEST_FILE="$STATE_DIR/latest-social-backup-manifest"
SOCIAL_BACKUP_LOG="$STATE_DIR/social-connection-backup.log"
SOCIAL_BACKUP_PID_FILE="$STATE_DIR/social-connection-backup.pid"
TUNNEL_TOKEN_FILE="$STATE_DIR/cloudflared-token"
LOCAL_BASE_URL="http://127.0.0.1:${PORT:-4175}"
RUNTIME_BIN="${AGENCY_LOCAL_RUNTIME_VENV:-/tmp/ai-native-content-agency-runtime}/bin/agency-api"
CLOUDFLARED_BIN="${AGENCY_CLOUDFLARED_BIN:-$STATE_DIR/bin/cloudflared}"

mkdir -p "$STATE_DIR"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  printf '%s\n' 'workspace_up_error=another recovery process is already running' >&2
  exit 75
fi

fail() {
  printf 'workspace_up_error=%s\n' "$1" >&2
  exit 1
}

health_ok() {
  curl --fail --silent --show-error --max-time 5 "$1/healthz" >/dev/null 2>&1
}

read_env_value() {
  local key="$1"
  python3 - "$ENV_FILE" "$key" <<'PY'
from pathlib import Path
import shlex
import sys
path = Path(sys.argv[1])
key = sys.argv[2]
if path.exists():
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(key + "="):
            values = shlex.split(line.split("=", 1)[1])
            print(values[0] if values else "")
            break
PY
}

set_env_value() {
  local key="$1"
  local value="$2"
  python3 - "$ENV_FILE" "$key" "$value" <<'PY'
from pathlib import Path
import shlex
import sys
path = Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]
lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
replacement = f"{key}={shlex.quote(value)}"
updated = []
replaced = False
for line in lines:
    if line.startswith(key + "="):
        if not replaced:
            updated.append(replacement)
            replaced = True
        continue
    updated.append(line)
if not replaced:
    updated.append(replacement)
path.write_text("\n".join(updated) + "\n", encoding="utf-8")
PY
}

force_fail_closed() {
  set_env_value AGENCY_SOCIAL_PUBLICATION_ENABLED false
  set_env_value AGENCY_POLITICAL_PUBLICATION_ENABLED false
  set_env_value AGENCY_POLITICAL_PAID_MEDIA_ENABLED false
}

environment_fingerprint() {
  [[ -f "$ENV_FILE" ]] || {
    printf '%s\n' 'missing'
    return 0
  }
  sha256sum "$ENV_FILE" | awk '{print $1}'
}

record_environment_fingerprint() {
  environment_fingerprint >"$RUNTIME_ENV_HASH_FILE"
}

runtime_environment_changed() {
  [[ -s "$RUNTIME_ENV_HASH_FILE" ]] || return 0
  local recorded current
  recorded="$(cat "$RUNTIME_ENV_HASH_FILE")"
  current="$(environment_fingerprint)"
  [[ "$recorded" != "$current" ]]
}

wait_for_health() {
  local base_url="$1"
  local attempts="$2"
  local delay="$3"
  for _ in $(seq 1 "$attempts"); do
    if health_ok "$base_url"; then
      return 0
    fi
    sleep "$delay"
  done
  return 1
}

launch_installed_api_background() {
  (
    cd "$ROOT_DIR"
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
    local host_value="${AGENCY_HOST:-127.0.0.1}"
    local port_value="${PORT:-4175}"
    local database_value="${AGENCY_MEMORY_DB:-$ROOT_DIR/.local/ai-native-content-agency-local.sqlite3}"
    local static_value="${AGENCY_STATIC_DIR:-$ROOT_DIR/dist}"
    local forwarded_value="${FORWARDED_ALLOW_IPS:-127.0.0.1}"
    nohup setsid env \
      AGENCY_HOST="$host_value" \
      PORT="$port_value" \
      AGENCY_MEMORY_DB="$database_value" \
      AGENCY_STATIC_DIR="$static_value" \
      FORWARDED_ALLOW_IPS="$forwarded_value" \
      "$RUNTIME_BIN" >"$API_LOG" 2>&1 < /dev/null 9>&- &
    printf '%s\n' "$!" >"$API_PID_FILE"
  )
}

start_installed_api() {
  [[ -x "$RUNTIME_BIN" ]] || return 1
  [[ -f "$ROOT_DIR/dist/index.html" ]] || return 1
  launch_installed_api_background
  wait_for_health "$LOCAL_BASE_URL" 30 1
}

start_product() {
  if health_ok "$LOCAL_BASE_URL"; then
    return 0
  fi
  if start_installed_api; then
    return 0
  fi
  (
    cd "$ROOT_DIR"
    nohup setsid npm run start:local >"$PRODUCT_LOG" 2>&1 < /dev/null 9>&- &
    printf '%s\n' "$!" >"$PRODUCT_PID_FILE"
  )
  wait_for_health "$LOCAL_BASE_URL" 180 2 || {
    tail -n 80 "$PRODUCT_LOG" >&2 || true
    fail 'local product did not become healthy'
  }
}

latest_quick_tunnel_url() {
  grep -hEo 'https://[a-z0-9-]+\.trycloudflare\.com' \
    "$TUNNEL_LOG" "$TUNNEL_STDOUT" 2>/dev/null | tail -n 1 || true
}

current_public_url() {
  local named_url discovered_url
  named_url="$(read_env_value AGENCY_CLOUDFLARE_PUBLIC_URL)"
  if [[ -n "$named_url" ]]; then
    printf '%s\n' "${named_url%/}"
    return 0
  fi
  discovered_url="$(latest_quick_tunnel_url)"
  if tunnel_process_alive && [[ -n "$discovered_url" ]] && health_ok "$discovered_url"; then
    printf '%s\n' "$discovered_url"
  elif [[ -s "$PUBLIC_URL_FILE" ]]; then
    cat "$PUBLIC_URL_FILE"
  else
    read_env_value AGENCY_PUBLIC_MEDIA_BASE_URL
  fi
}

tunnel_process_alive() {
  local pid=""
  if [[ -s "$TUNNEL_PID_FILE" ]]; then
    pid="$(cat "$TUNNEL_PID_FILE")"
  else
    pid="$(pgrep -f 'cloudflared tunnel .*run|cloudflared tunnel --protocol http2 --url http://127\.0\.0\.1:[0-9]+' | head -n 1 || true)"
    if [[ "$pid" =~ ^[0-9]+$ ]]; then
      printf '%s\n' "$pid" >"$TUNNEL_PID_FILE"
    fi
  fi
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null
}

stop_stale_tunnel() {
  if [[ -s "$TUNNEL_PID_FILE" ]]; then
    local stale_pid
    stale_pid="$(cat "$TUNNEL_PID_FILE")"
    if [[ "$stale_pid" =~ ^[0-9]+$ ]]; then
      kill "$stale_pid" 2>/dev/null || true
    fi
  fi
  rm -f "$TUNNEL_PID_FILE"
}

validate_public_url() {
  local value="$1"
  [[ "$value" =~ ^https://[A-Za-z0-9.-]+$ ]] || fail 'public URL must be an HTTPS origin without a path'
}

start_named_tunnel() {
  local token public_url
  token="$(read_env_value AGENCY_CLOUDFLARE_TUNNEL_TOKEN)"
  public_url="$(read_env_value AGENCY_CLOUDFLARE_PUBLIC_URL)"
  [[ -n "$token" && -n "$public_url" ]] || fail 'named Cloudflare tunnel requires token and public URL'
  public_url="${public_url%/}"
  validate_public_url "$public_url"
  if tunnel_process_alive && health_ok "$public_url"; then
    printf '%s\n' "$public_url"
    return 0
  fi
  [[ -x "$CLOUDFLARED_BIN" ]] || fail 'cloudflared binary is unavailable'
  stop_stale_tunnel
  umask 077
  printf '%s' "$token" >"$TUNNEL_TOKEN_FILE"
  chmod 600 "$TUNNEL_TOKEN_FILE"
  : >"$TUNNEL_LOG"
  : >"$TUNNEL_STDOUT"
  nohup "$CLOUDFLARED_BIN" tunnel --no-autoupdate --protocol http2 \
    --logfile "$TUNNEL_LOG" --loglevel info \
    run --token-file "$TUNNEL_TOKEN_FILE" --url "$LOCAL_BASE_URL" \
    >"$TUNNEL_STDOUT" 2>&1 < /dev/null 9>&- &
  printf '%s\n' "$!" >"$TUNNEL_PID_FILE"
  for _ in $(seq 1 90); do
    if tunnel_process_alive && health_ok "$public_url"; then
      printf '%s\n' "$public_url"
      return 0
    fi
    sleep 1
  done
  tail -n 80 "$TUNNEL_LOG" "$TUNNEL_STDOUT" >&2 || true
  fail 'named Cloudflare tunnel did not become healthy'
}

start_quick_tunnel() {
  local existing_url discovered_url
  existing_url="$(current_public_url || true)"
  discovered_url="$(latest_quick_tunnel_url)"
  if tunnel_process_alive && [[ -n "$discovered_url" ]] && health_ok "$discovered_url"; then
    printf '%s\n' "$discovered_url"
    return 0
  fi
  if tunnel_process_alive && [[ "$existing_url" == https://*.trycloudflare.com ]] && health_ok "$existing_url"; then
    printf '%s\n' "$existing_url"
    return 0
  fi
  if [[ -s "$TUNNEL_PID_FILE" ]]; then
    local stale_pid
    stale_pid="$(cat "$TUNNEL_PID_FILE")"
    if [[ "$stale_pid" =~ ^[0-9]+$ ]]; then
      kill "$stale_pid" 2>/dev/null || true
    fi
  fi
  : >"$TUNNEL_LOG"
  : >"$TUNNEL_STDOUT"
  nohup "$CLOUDFLARED_BIN" tunnel --protocol http2 --url "$LOCAL_BASE_URL" \
    --logfile "$TUNNEL_LOG" --loglevel info \
    >"$TUNNEL_STDOUT" 2>&1 < /dev/null 9>&- &
  printf '%s\n' "$!" >"$TUNNEL_PID_FILE"

  local public_url=""
  for _ in $(seq 1 90); do
    public_url="$(grep -hEo 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" "$TUNNEL_STDOUT" 2>/dev/null | tail -n 1 || true)"
    if [[ -n "$public_url" ]] && health_ok "$public_url"; then
      printf '%s\n' "$public_url"
      return 0
    fi
    sleep 1
  done
  tail -n 80 "$TUNNEL_LOG" "$TUNNEL_STDOUT" >&2 || true
  fail 'quick tunnel did not become healthy'
}

start_tunnel() {
  local token public_url
  token="$(read_env_value AGENCY_CLOUDFLARE_TUNNEL_TOKEN)"
  public_url="$(read_env_value AGENCY_CLOUDFLARE_PUBLIC_URL)"
  if [[ -n "$token" || -n "$public_url" ]]; then
    [[ -n "$token" && -n "$public_url" ]] || fail 'named Cloudflare tunnel configuration is incomplete'
    start_named_tunnel
  else
    start_quick_tunnel
  fi
}

social_backup_process_alive() {
  local pid=""
  if [[ -s "$SOCIAL_BACKUP_PID_FILE" ]]; then
    pid="$(cat "$SOCIAL_BACKUP_PID_FILE")"
  fi
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null
}

start_social_backup_watchdog() {
  local database_value
  database_value="$(read_env_value AGENCY_MEMORY_DB)"
  database_value="${database_value:-$ROOT_DIR/.local/ai-native-content-agency-local.sqlite3}"
  [[ -z "$(read_env_value AGENCY_DATABASE_URL)" ]] || return 0
  [[ -f "$database_value" ]] || return 0
  if social_backup_process_alive; then
    return 0
  fi
  mkdir -p "$SOCIAL_BACKUP_DIR"
  chmod 700 "$SOCIAL_BACKUP_DIR"
  : >"$SOCIAL_BACKUP_LOG"
  nohup setsid python3 "$ROOT_DIR/scripts/watch-social-connection-backups.py" \
    --database "$database_value" \
    --output-dir "$SOCIAL_BACKUP_DIR" \
    --state-file "$SOCIAL_BACKUP_STATE_FILE" \
    --manifest-file "$SOCIAL_BACKUP_MANIFEST_FILE" \
    --poll-seconds 10 \
    >"$SOCIAL_BACKUP_LOG" 2>&1 < /dev/null 9>&- &
  printf '%s\n' "$!" >"$SOCIAL_BACKUP_PID_FILE"
  for _ in $(seq 1 20); do
    if social_backup_process_alive && [[ -s "$SOCIAL_BACKUP_STATE_FILE" ]]; then
      return 0
    fi
    sleep 1
  done
  tail -n 80 "$SOCIAL_BACKUP_LOG" >&2 || true
  fail 'social connection backup watchdog did not become ready'
}

backup_social_connections_once() {
  local database_value
  database_value="$(read_env_value AGENCY_MEMORY_DB)"
  database_value="${database_value:-$ROOT_DIR/.local/ai-native-content-agency-local.sqlite3}"
  [[ -z "$(read_env_value AGENCY_DATABASE_URL)" ]] || fail 'local social backup supports SQLite only'
  python3 "$ROOT_DIR/scripts/watch-social-connection-backups.py" \
    --database "$database_value" \
    --output-dir "$SOCIAL_BACKUP_DIR" \
    --state-file "$SOCIAL_BACKUP_STATE_FILE" \
    --manifest-file "$SOCIAL_BACKUP_MANIFEST_FILE" \
    --once
}

restart_api_with_current_environment() {
  [[ -x "$RUNTIME_BIN" ]] || fail 'installed runtime binary is missing'
  local pid
  while read -r pid; do
    [[ "$pid" =~ ^[0-9]+$ ]] || continue
    kill "$pid" 2>/dev/null || true
  done < <(pgrep -f '^/tmp/ai-native-content-agency-runtime/bin/python /tmp/ai-native-content-agency-runtime/bin/agency-api$' || true)
  for _ in $(seq 1 30); do
    if ! pgrep -f '^/tmp/ai-native-content-agency-runtime/bin/python /tmp/ai-native-content-agency-runtime/bin/agency-api$' >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
  launch_installed_api_background
  wait_for_health "$LOCAL_BASE_URL" 60 1 || {
    tail -n 80 "$API_LOG" >&2 || true
    fail 'API did not restart with the refreshed public URL'
  }
}

status() {
  local public_url
  public_url="$(current_public_url || true)"
  printf 'workspace_root=%s\n' "$ROOT_DIR"
  printf 'local_health=%s\n' "$(health_ok "$LOCAL_BASE_URL" && printf healthy || printf unavailable)"
  printf 'public_url=%s\n' "${public_url:-not_configured}"
  if [[ -n "$public_url" ]]; then
    printf 'public_health=%s\n' "$(health_ok "$public_url" && printf healthy || printf unavailable)"
  else
    printf 'public_health=not_configured\n'
  fi
  printf 'tunnel_process=%s\n' "$(tunnel_process_alive && printf running || printf stopped)"
  if [[ -n "$(read_env_value AGENCY_CLOUDFLARE_TUNNEL_TOKEN)" ]]; then
    printf 'tunnel_mode=named\n'
  else
    printf 'tunnel_mode=quick\n'
  fi
  printf 'social_backup_watchdog=%s\n' "$(social_backup_process_alive && printf running || printf stopped)"
  if [[ -s "$SOCIAL_BACKUP_MANIFEST_FILE" ]]; then
    printf 'latest_social_backup=available\n'
  else
    printf 'latest_social_backup=unavailable\n'
  fi
  printf 'social_publication_enabled=%s\n' "$(read_env_value AGENCY_SOCIAL_PUBLICATION_ENABLED)"
  printf 'political_publication_enabled=%s\n' "$(read_env_value AGENCY_POLITICAL_PUBLICATION_ENABLED)"
  printf 'political_paid_media_enabled=%s\n' "$(read_env_value AGENCY_POLITICAL_PAID_MEDIA_ENABLED)"
  printf 'runtime_environment=%s\n' "$(runtime_environment_changed && printf stale || printf current)"
}

up() {
  force_fail_closed
  start_product
  start_social_backup_watchdog
  local previous_url public_url
  previous_url="$(read_env_value AGENCY_PUBLIC_MEDIA_BASE_URL)"
  public_url="$(start_tunnel)"
  printf '%s\n' "$public_url" >"$PUBLIC_URL_FILE"
  set_env_value AGENCY_PUBLIC_MEDIA_BASE_URL "$public_url"
  set_env_value AGENCY_INSTAGRAM_REDIRECT_URI "$public_url/api/v1/social-channels/instagram/oauth/callback"
  set_env_value AGENCY_X_REDIRECT_URI "$public_url/api/v1/social-channels/x/oauth/callback"
  if [[ "$previous_url" != "$public_url" ]] || runtime_environment_changed; then
    restart_api_with_current_environment
  fi
  record_environment_fingerprint
  health_ok "$public_url" || fail 'public endpoint is not healthy after recovery'
  printf 'workspace_up=ready\n'
  printf 'public_url=%s\n' "$public_url"
  printf 'instagram_callback=%s/api/v1/social-channels/instagram/oauth/callback\n' "$public_url"
  printf 'x_callback=%s/api/v1/social-channels/x/oauth/callback\n' "$public_url"
  printf 'effect_switches=fail_closed\n'
}

case "${1:-up}" in
  up) up ;;
  status) status ;;
  url) current_public_url ;;
  backup) backup_social_connections_once ;;
  *) printf 'usage: %s [up|status|url|backup]\n' "$0" >&2; exit 64 ;;
esac
