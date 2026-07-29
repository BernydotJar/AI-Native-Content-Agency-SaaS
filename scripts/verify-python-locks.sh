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

"$PYTHON_BIN" -m venv "$TMP_DIR/compat-build-venv"
COMPAT_BUILD_PYTHON="$TMP_DIR/compat-build-venv/bin/python"
"$COMPAT_BUILD_PYTHON" -m pip install --disable-pip-version-check --require-hashes \
  -r "$REPOSITORY_ROOT/backend/requirements-local-build.lock"
"$COMPAT_BUILD_PYTHON" -m pip wheel --disable-pip-version-check \
  --no-deps --no-build-isolation --wheel-dir "$TMP_DIR/compat-wheels" \
  "$REPOSITORY_ROOT/backend"

"$PYTHON_BIN" -m venv "$TMP_DIR/test-venv"
TEST_PYTHON="$TMP_DIR/test-venv/bin/python"
"$TEST_PYTHON" -m pip install --disable-pip-version-check --require-hashes \
  -r "$REPOSITORY_ROOT/backend/requirements-test.lock"
"$TEST_PYTHON" -m pip install --disable-pip-version-check --no-deps \
  "$TMP_DIR"/wheels/*.whl
"$TEST_PYTHON" -m pip check
SEMANTIC_ARGS=()
if [[ "${SEMANTIC_EVAL_ALLOW_DIRTY:-0}" == "1" ]]; then
  SEMANTIC_ARGS+=(--allow-dirty)
elif [[ "${SEMANTIC_EVAL_ALLOW_DIRTY:-0}" != "0" ]]; then
  echo "SEMANTIC_EVAL_ALLOW_DIRTY must be 0 or 1" >&2
  exit 2
fi
"$TEST_PYTHON" "$REPOSITORY_ROOT/scripts/verify-semantic-evals.py" "${SEMANTIC_ARGS[@]}"
"$TEST_PYTHON" "$REPOSITORY_ROOT/scripts/verify-semantic-evals-independent.py" "${SEMANTIC_ARGS[@]}"
"$TEST_PYTHON" -m unittest discover -s "$REPOSITORY_ROOT/backend/tests" -v

"$TEST_PYTHON" - <<'PY'
from importlib.metadata import version

for package in ("agency-runtime", "fastapi", "starlette", "uvicorn", "pydantic", "httpx"):
    print(f"{package}={version(package)}")
PY
