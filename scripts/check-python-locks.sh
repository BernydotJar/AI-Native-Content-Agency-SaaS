#!/usr/bin/env bash
set -euo pipefail

REPOSITORY_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
TMP_DIR=$(mktemp -d)
LOCKS=(requirements.lock requirements-test.lock requirements-build.lock requirements-local-build.lock)

restore() {
  for lock in "${LOCKS[@]}"; do
    if [ -f "$TMP_DIR/$lock" ]; then
      cp "$TMP_DIR/$lock" "$REPOSITORY_ROOT/backend/$lock"
    fi
  done
  rm -rf "$TMP_DIR"
}
trap restore EXIT

for lock in "${LOCKS[@]}"; do
  cp "$REPOSITORY_ROOT/backend/$lock" "$TMP_DIR/$lock"
done

"$REPOSITORY_ROOT/scripts/update-python-locks.sh"

status=0
for lock in "${LOCKS[@]}"; do
  if ! diff -u "$TMP_DIR/$lock" "$REPOSITORY_ROOT/backend/$lock"; then
    status=1
  fi
done

if [ "$status" -ne 0 ]; then
  printf 'Python lockfiles are stale. Run scripts/update-python-locks.sh and commit the result.\n' >&2
  exit "$status"
fi

printf 'python_lockfiles=up_to_date\n'
