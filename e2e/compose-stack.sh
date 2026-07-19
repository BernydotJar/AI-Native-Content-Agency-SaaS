#!/usr/bin/env bash
set -euo pipefail

E2E_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${E2E_ROOT}"

if [[ -z "${COMPOSE_PROJECT_NAME:-}" ]]; then
  COMPOSE_PROJECT_NAME="agency-e2e-$(date +%s)-${$}"
fi
if [[ "${COMPOSE_PROJECT_NAME}" != agency-e2e-* ]]; then
  echo "COMPOSE_PROJECT_NAME must use the owned disposable agency-e2e-* prefix" >&2
  exit 2
fi
export COMPOSE_PROJECT_NAME
export IMAGE_TAG="${IMAGE_TAG:-e2e}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-e2e-compose-only}"
export E2E_RESTART_PERSISTENCE="1"

cleanup() {
  if [[ "${COMPOSE_PROJECT_NAME}" != agency-e2e-* ]]; then
    echo "refusing volume cleanup for unexpected Compose project" >&2
    return 1
  fi
  docker compose down --remove-orphans --volumes
}

dump_logs() {
  docker compose logs --no-color database migrate app || true
}

trap cleanup EXIT

# The application binds a fixed loopback port. Stop the ordinary local project
# without deleting its database, then use a unique E2E project whose volume is
# always removed so no result can replay state from an earlier invocation.
if [[ "${COMPOSE_PROJECT_NAME}" != "ai-native-content-agency" ]]; then
  docker compose --project-name ai-native-content-agency down --remove-orphans
fi
cleanup

if ! docker compose up --build --detach --wait --wait-timeout 180; then
  dump_logs
  exit 1
fi

if ! npm run test:e2e; then
  dump_logs
  exit 1
fi
