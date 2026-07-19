#!/usr/bin/env bash
set -euo pipefail

POSTGRES_GATE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${POSTGRES_GATE_ROOT}"

# A generated project name and deleted volume make every invocation independent
# from prior local, CI, or evaluator state. The prefix also constrains cleanup to
# this gate's own Compose resources.
POSTGRES_GATE_PROJECT="agency-pg-eval-$(date +%s)-${$}"
export COMPOSE_PROJECT_NAME="${POSTGRES_GATE_PROJECT}"
export IMAGE_TAG="postgres-integration"
export POSTGRES_PASSWORD="postgres-integration-only"

cleanup() {
  if [[ "${COMPOSE_PROJECT_NAME}" != agency-pg-eval-* ]]; then
    echo "refusing cleanup for unexpected Compose project" >&2
    return 1
  fi
  docker compose --profile integration down --remove-orphans --volumes
}

dump_logs() {
  docker compose --profile integration logs --no-color database migrate || true
}

trap cleanup EXIT
cleanup

docker compose --profile integration build migrate postgres-integration
if ! docker compose --profile integration up --detach --wait --wait-timeout 120 database; then
  dump_logs
  exit 1
fi
if ! docker compose --profile integration run --rm migrate; then
  dump_logs
  exit 1
fi
if ! docker compose --profile integration run \
  --rm \
  --no-deps \
  postgres-integration; then
  dump_logs
  exit 1
fi
