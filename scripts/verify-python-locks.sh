#!/usr/bin/env bash
set -euo pipefail

REPOSITORY_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PYTHON_BIN=${PYTHON_BIN:-python3}
TMP_DIR=$(mktemp -d)
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

"$PYTHON_BIN" -m venv "$TMP_DIR/build-venv"
BUILD_PYTHON="$TMP_DIR/build-venv/bin/python"
"$BUILD_PYTHON" -m pip install --disable-pip-version-check --require-hashes \
  -r "$REPOSITORY_ROOT/backend/requirements-build.lock"
"$BUILD_PYTHON" -m build --no-isolation --wheel --outdir "$TMP_DIR/wheels" \
  "$REPOSITORY_ROOT/backend"

"$PYTHON_BIN" -m venv "$TMP_DIR/test-venv"
TEST_PYTHON="$TMP_DIR/test-venv/bin/python"
"$TEST_PYTHON" -m pip install --disable-pip-version-check --require-hashes \
  -r "$REPOSITORY_ROOT/backend/requirements-test.lock"
"$TEST_PYTHON" -m pip install --disable-pip-version-check --no-deps \
  "$TMP_DIR"/wheels/*.whl
"$TEST_PYTHON" -m pip check
"$TEST_PYTHON" -m unittest discover -s "$REPOSITORY_ROOT/backend/tests" -v

"$TEST_PYTHON" - <<'PY'
from importlib.metadata import version

for package in ("agency-runtime", "fastapi", "starlette", "uvicorn", "pydantic", "httpx"):
    print(f"{package}={version(package)}")
PY
