#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fail() {
  printf '%s\n' "$1" >&2
  exit 65
}
LOCAL_ENV_FILE="${AGENCY_ENV_FILE:-$ROOT_DIR/.env.local}"
if [[ -f "$LOCAL_ENV_FILE" ]]; then
  if [[ "$LOCAL_ENV_FILE" == "$ROOT_DIR/"* ]]; then
    relative_env="${LOCAL_ENV_FILE#$ROOT_DIR/}"
    if git -C "$ROOT_DIR" ls-files --error-unmatch "$relative_env" >/dev/null 2>&1; then
      printf 'refusing tracked local environment file: %s
' "$relative_env" >&2
      exit 66
    fi
  fi
  set -a
  # shellcheck disable=SC1090
  source "$LOCAL_ENV_FILE"
  set +a
  printf '[local-product] loaded local environment: %s (values hidden)
' "$(basename "$LOCAL_ENV_FILE")"
fi

validate_social_bootstrap_environment() {
  local tenant="${AGENCY_SOCIAL_BOOTSTRAP_TENANT_ID:-}"
  local x_fields=(
    AGENCY_X_USER_ACCESS_TOKEN
    AGENCY_X_USER_ACCESS_TOKEN_SECRET
    AGENCY_X_ACCOUNT_ID
    AGENCY_X_ACCOUNT_USERNAME
  )
  local instagram_fields=(
    AGENCY_INSTAGRAM_ACCESS_TOKEN
    AGENCY_INSTAGRAM_ACCOUNT_ID
    AGENCY_INSTAGRAM_ACCOUNT_USERNAME
  )
  local x_configured=0
  local instagram_configured=0
  local field=""

  for field in "${x_fields[@]}"; do
    if [[ -n "${!field:-}" ]]; then
      x_configured=$((x_configured + 1))
    fi
  done
  for field in "${instagram_fields[@]}"; do
    if [[ -n "${!field:-}" ]]; then
      instagram_configured=$((instagram_configured + 1))
    fi
  done

  if [[ -n "$tenant" && $x_configured -eq 0 && $instagram_configured -eq 0 ]]; then
    printf '%s\n' 'social bootstrap configuration is incomplete: clear AGENCY_SOCIAL_BOOTSTRAP_TENANT_ID for OAuth-only setup, or provide a complete X/Instagram token group' >&2
    return 65
  fi
  if [[ -z "$tenant" && ( $x_configured -gt 0 || $instagram_configured -gt 0 ) ]]; then
    printf '%s\n' 'social bootstrap configuration is incomplete: set AGENCY_SOCIAL_BOOTSTRAP_TENANT_ID when bootstrap tokens are provided' >&2
    return 65
  fi
  if [[ $x_configured -ne 0 && $x_configured -ne ${#x_fields[@]} ]]; then
    printf '%s\n' 'X social bootstrap configuration is incomplete; provide all X token/account fields or leave all of them empty' >&2
    return 65
  fi
  if [[ $instagram_configured -ne 0 && $instagram_configured -ne ${#instagram_fields[@]} ]]; then
    printf '%s\n' 'Instagram social bootstrap configuration is incomplete; provide token, account ID and username or leave all of them empty' >&2
    return 65
  fi
}
validate_social_bootstrap_environment || exit $?

MODE="run"
if [[ "${1:-}" == "--check" ]]; then
  MODE="check"
elif [[ $# -gt 0 ]]; then
  printf 'usage: %s [--check]\n' "$0" >&2
  exit 64
fi

HOST="${AGENCY_HOST:-127.0.0.1}"
PORT_VALUE="${PORT:-4175}"
DATABASE_PATH="${AGENCY_MEMORY_DB:-$ROOT_DIR/.local/ai-native-content-agency-local.sqlite3}"
BUILD_VENV="${AGENCY_LOCAL_BUILD_VENV:-/tmp/ai-native-content-agency-build}"
RUNTIME_VENV="${AGENCY_LOCAL_RUNTIME_VENV:-/tmp/ai-native-content-agency-runtime}"
WHEEL_DIR="${AGENCY_LOCAL_WHEEL_DIR:-/tmp/ai-native-content-agency-wheels}"
PRIMARY_BUILD_LOCK="${AGENCY_LOCAL_PRIMARY_BUILD_LOCK:-$ROOT_DIR/backend/requirements-build.lock}"
COMPATIBILITY_BUILD_LOCK="${AGENCY_LOCAL_COMPATIBILITY_BUILD_LOCK:-$ROOT_DIR/backend/requirements-local-build.lock}"

python_is_supported() {
  "$1" -c 'import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] < (3, 14) else 1)' \
    >/dev/null 2>&1
}

select_python() {
  local candidate=""
  if [[ -n "${AGENCY_PYTHON_BIN:-}" ]]; then
    if ! command -v "$AGENCY_PYTHON_BIN" >/dev/null 2>&1; then
      printf 'AGENCY_PYTHON_BIN was not found: %s\n' "$AGENCY_PYTHON_BIN" >&2
      return 1
    fi
    candidate="$(command -v "$AGENCY_PYTHON_BIN")"
    if ! python_is_supported "$candidate"; then
      printf 'AGENCY_PYTHON_BIN must be Python 3.11 through 3.13: %s (%s)\n' \
        "$candidate" "$($candidate --version 2>&1 || printf unknown)" >&2
      return 1
    fi
    printf '%s\n' "$candidate"
    return 0
  fi

  for candidate in python3 python3.13 python3.12 python3.11; do
    if command -v "$candidate" >/dev/null 2>&1; then
      candidate="$(command -v "$candidate")"
      if python_is_supported "$candidate"; then
        printf '%s\n' "$candidate"
        return 0
      fi
    fi
  done

  printf 'Python 3.11 through 3.13 is required. Install a supported interpreter or set AGENCY_PYTHON_BIN.\n' >&2
  return 1
}

if [[ "$HOST" != "127.0.0.1" && "$HOST" != "localhost" ]]; then
  printf 'local product runner refuses non-loopback host: %s\n' "$HOST" >&2
  exit 65
fi
if [[ ! "$PORT_VALUE" =~ ^[0-9]+$ ]] || (( PORT_VALUE < 1024 || PORT_VALUE > 65535 )); then
  printf 'PORT must be an integer from 1024 through 65535\n' >&2
  exit 65
fi
for command_name in node npm; do
  command -v "$command_name" >/dev/null 2>&1 || {
    printf 'required command not found: %s\n' "$command_name" >&2
    exit 69
  }
done

PYTHON_BIN="$(select_python)" || exit 69
PYTHON_VERSION="$($PYTHON_BIN -c 'import platform; print(platform.python_version())')"

GENERATED_LOCAL_KEY=""
if [[ -z "${AGENCY_IDENTITY_CREDENTIALS_JSON:-}" ]]; then
  GENERATED_LOCAL_KEY="$($PYTHON_BIN - <<'PY'
import secrets
print("local-" + secrets.token_urlsafe(36))
PY
)"
  export AGENCY_IDENTITY_CREDENTIALS_JSON="$($PYTHON_BIN - "$GENERATED_LOCAL_KEY" <<'PY'
import json
import sys
print(json.dumps([{
    "tenant_id": "local-tenant",
    "subject_id": "local-admin",
    "role": "admin",
    "key_id": "local-ephemeral-v1",
    "api_key": sys.argv[1],
    "active": True,
}], separators=(",", ":")))
PY
)"
fi

export AGENCY_HOST="$HOST"
export PORT="$PORT_VALUE"
if [[ "$MODE" == "run" ]]; then
  mkdir -p "$(dirname "$DATABASE_PATH")"
fi
export AGENCY_MEMORY_DB="$DATABASE_PATH"
export AGENCY_STATIC_DIR="$ROOT_DIR/dist"
export AGENCY_SESSION_COOKIE_SAMESITE="${AGENCY_SESSION_COOKIE_SAMESITE:-lax}"
if [[ -z "${AGENCY_SESSION_COOKIE_SECURE+x}" ]]; then
  if [[ "${AGENCY_X_REDIRECT_URI:-}" == https://* || "${AGENCY_INSTAGRAM_REDIRECT_URI:-}" == https://* ]]; then
    export AGENCY_SESSION_COOKIE_SECURE=true
  else
    export AGENCY_SESSION_COOKIE_SECURE=false
  fi
fi
export FORWARDED_ALLOW_IPS=127.0.0.1

if [[ "$MODE" == "check" ]]; then
  printf 'local_product_config=pass\n'
  printf 'host=%s\n' "$HOST"
  printf 'port=%s\n' "$PORT_VALUE"
  printf 'static_dir=%s\n' "$AGENCY_STATIC_DIR"
  printf 'database_backend=sqlite\n'
  printf 'python_bin=%s\n' "$PYTHON_BIN"
  printf 'python_version=%s\n' "$PYTHON_VERSION"
  printf 'identity_source=%s\n' "$([[ -n "$GENERATED_LOCAL_KEY" ]] && printf ephemeral || printf environment)"
  printf 'session_cookie_secure=%s\n' "$AGENCY_SESSION_COOKIE_SECURE"
  public_media_base_url="${AGENCY_PUBLIC_MEDIA_BASE_URL:-}"
  public_media_signing_keys="${AGENCY_PUBLIC_MEDIA_SIGNING_KEYS_JSON:-}"
  public_media_active_key="${AGENCY_PUBLIC_MEDIA_ACTIVE_SIGNING_KEY_ID:-}"
  public_media_legacy_key="${AGENCY_PUBLIC_MEDIA_SIGNING_KEY:-}"
  public_media_ttl="${AGENCY_PUBLIC_MEDIA_TTL_SECONDS:-86400}"
  if [ -n "$public_media_legacy_key" ] && { [ -n "$public_media_signing_keys" ] || [ -n "$public_media_active_key" ]; }; then
    fail "legacy and keyring public media signing configuration are mutually exclusive"
  fi
  if { [ -n "$public_media_signing_keys" ] && [ -z "$public_media_active_key" ]; } || \
     { [ -z "$public_media_signing_keys" ] && [ -n "$public_media_active_key" ]; }; then
    fail "AGENCY_PUBLIC_MEDIA_SIGNING_KEYS_JSON and AGENCY_PUBLIC_MEDIA_ACTIVE_SIGNING_KEY_ID must be configured together"
  fi
  public_media_signing_configured=false
  public_media_signing_mode=disabled
  if [ -n "$public_media_legacy_key" ]; then
    public_media_signing_configured=true
    public_media_signing_mode=legacy
  elif [ -n "$public_media_signing_keys" ]; then
    public_media_signing_configured=true
    public_media_signing_mode=keyring
  fi
  if { [ -n "$public_media_base_url" ] && [ "$public_media_signing_configured" != true ]; } || \
     { [ -z "$public_media_base_url" ] && [ "$public_media_signing_configured" = true ]; }; then
    fail "AGENCY_PUBLIC_MEDIA_BASE_URL and a public media signing configuration must be configured together"
  fi
  case "$public_media_ttl" in
    ''|*[!0-9]*) fail "AGENCY_PUBLIC_MEDIA_TTL_SECONDS must be an integer" ;;
  esac
  if [ "$public_media_ttl" -lt 900 ] || [ "$public_media_ttl" -gt 604800 ]; then
    fail "AGENCY_PUBLIC_MEDIA_TTL_SECONDS must be between 900 and 604800"
  fi
  if [ -n "$public_media_base_url" ]; then
    printf 'public_media_configured=true\n'
  else
    printf 'public_media_configured=false\n'
  fi
  printf 'public_media_signing_mode=%s\n' "$public_media_signing_mode"
  printf 'public_media_ttl_seconds=%s\n' "$public_media_ttl"
  printf 'session_cookie_samesite=%s\n' "$AGENCY_SESSION_COOKIE_SAMESITE"
  printf 'build_lock_strategy=primary_then_hash_locked_compatibility\n'
  printf 'external_provider_calls=not_started\n'
  exit 0
fi

cd "$ROOT_DIR"
printf '[local-product] building production web bundle\n'
npm run build

printf '[local-product] building hash-locked Python wheel\n'
rm -rf "$RUNTIME_VENV" "$WHEEL_DIR"

install_build_toolchain() {
  local lock_path="$1"
  rm -rf "$BUILD_VENV"
  "$PYTHON_BIN" -m venv "$BUILD_VENV"
  "$BUILD_VENV/bin/python" -m pip install --disable-pip-version-check \
    --require-hashes -r "$lock_path"
}

ACTIVE_BUILD_LOCK="$PRIMARY_BUILD_LOCK"
ACTIVE_BUILD_COMMAND="build"
if ! install_build_toolchain "$PRIMARY_BUILD_LOCK"; then
  printf '[local-product] primary build lock is unavailable from this package index; retrying the hash-locked compatibility toolchain\n' >&2
  ACTIVE_BUILD_LOCK="$COMPATIBILITY_BUILD_LOCK"
  ACTIVE_BUILD_COMMAND="pip-wheel"
  install_build_toolchain "$COMPATIBILITY_BUILD_LOCK"
fi

printf '[local-product] build toolchain lock: %s\n' "$(basename "$ACTIVE_BUILD_LOCK")"
mkdir -p "$WHEEL_DIR"
if [[ "$ACTIVE_BUILD_COMMAND" == "build" ]]; then
  "$BUILD_VENV/bin/python" -m build --no-isolation --wheel \
    --outdir "$WHEEL_DIR" backend
else
  "$BUILD_VENV/bin/python" -m pip wheel --disable-pip-version-check \
    --no-deps --no-build-isolation --wheel-dir "$WHEEL_DIR" "$ROOT_DIR/backend"
fi

printf '[local-product] installing hash-locked runtime\n'
"$PYTHON_BIN" -m venv "$RUNTIME_VENV"
"$RUNTIME_VENV/bin/python" -m pip install --disable-pip-version-check \
  --require-hashes -r backend/requirements.lock
"$RUNTIME_VENV/bin/python" -m pip install --disable-pip-version-check \
  --no-deps "$WHEEL_DIR"/*.whl
"$RUNTIME_VENV/bin/python" -m pip check

printf '\nProducto local: http://%s:%s\n' "$HOST" "$PORT_VALUE"
printf 'Tenant: local-tenant\n'
if [[ -n "$GENERATED_LOCAL_KEY" ]]; then
  printf 'Credencial local efímera (se muestra una vez): %s\n' "$GENERATED_LOCAL_KEY"
  printf 'La credencial cambia al reiniciar; define AGENCY_IDENTITY_CREDENTIALS_JSON para una identidad local estable.\n'
else
  printf 'Identidad: AGENCY_IDENTITY_CREDENTIALS_JSON proporcionado por el operador.\n'
fi
printf 'Detén el runtime con Ctrl+C.\n\n'

"$RUNTIME_VENV/bin/agency-api"
