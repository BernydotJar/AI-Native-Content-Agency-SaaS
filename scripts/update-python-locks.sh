#!/usr/bin/env bash
set -euo pipefail

REPOSITORY_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PYTHON_BIN=${PYTHON_BIN:-python3}
TMP_DIR=$(mktemp -d)
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

"$PYTHON_BIN" -m venv "$TMP_DIR/venv"
PYTHON="$TMP_DIR/venv/bin/python"
"$PYTHON" -m pip install --disable-pip-version-check --require-hashes \
  -r "$REPOSITORY_ROOT/backend/requirements-build.lock"

cd "$REPOSITORY_ROOT/backend"
"$TMP_DIR/venv/bin/pip-compile" --resolver=backtracking --generate-hashes \
  --strip-extras --output-file=requirements.lock requirements.in
"$TMP_DIR/venv/bin/pip-compile" --resolver=backtracking --generate-hashes \
  --strip-extras --output-file=requirements-test.lock requirements-test.in
"$TMP_DIR/venv/bin/pip-compile" --resolver=backtracking --generate-hashes \
  --strip-extras --allow-unsafe --output-file=requirements-build.lock \
  requirements-build.in
"$TMP_DIR/venv/bin/pip-compile" --resolver=backtracking --generate-hashes \
  --strip-extras --allow-unsafe --output-file=requirements-local-build.lock \
  requirements-local-build.in
