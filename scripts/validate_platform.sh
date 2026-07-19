#!/usr/bin/env bash
set -euo pipefail

PLATFORM_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PLATFORM_ROOT}"

export TF_IN_AUTOMATION=1
export TF_INPUT=0
export PYTHONPYCACHEPREFIX="${TMPDIR:-/tmp}/agency-platform-pycache"

if [[ -x "${PLATFORM_ROOT}/backend/.venv/bin/python" ]]; then
  PLATFORM_PYTHON="${PLATFORM_ROOT}/backend/.venv/bin/python"
else
  PLATFORM_PYTHON="${PYTHON:-python3}"
fi

if ! command -v "${PLATFORM_PYTHON}" >/dev/null 2>&1; then
  printf 'platform_validation=FAIL missing_python=%s\n' "${PLATFORM_PYTHON}" >&2
  exit 1
fi

terraform fmt -check -recursive infra

TERRAFORM_CONFIGS=(
  infra/modules/project_services
  infra/modules/github_wif
  infra/modules/artifact_registry
  infra/modules/cloud_sql
  infra/modules/cloud_run
  infra/modules/observability
  infra/bootstrap
  infra/environments/dev
  infra/environments/dev_runtime
)

for config in "${TERRAFORM_CONFIGS[@]}"; do
  terraform -chdir="${config}" init -backend=false -input=false -lockfile=readonly
  terraform -chdir="${config}" validate
done

terraform -chdir=infra/bootstrap test
terraform -chdir=infra/environments/dev test
terraform -chdir=infra/environments/dev_runtime test
terraform -chdir=infra/modules/artifact_registry test
terraform -chdir=infra/modules/observability test

"${PLATFORM_PYTHON}" -m py_compile \
  scripts/check_yaml.py \
  scripts/dev_apply_gate.py \
  scripts/eval_harness.py \
  scripts/gcp_permission_preflight.py \
  scripts/generate_ts_contracts.py \
  scripts/governance_eval.py \
  scripts/http_smoke.py \
  scripts/platform_eval.py \
  scripts/post_apply_verify.py \
  scripts/repository_integrity.py \
  scripts/rollback_image_gate.py \
  scripts/run_cloud_migrations.py \
  scripts/start_container.py \
  scripts/terraform_plan_gate.py
"${PLATFORM_PYTHON}" -m unittest \
  scripts.test_dev_apply_gate \
  scripts.test_eval_harness \
  scripts.test_gcp_permission_preflight \
  scripts.test_governance_eval \
  scripts.test_http_smoke \
  scripts.test_post_apply_verify \
  scripts.test_repository_integrity \
  scripts.test_rollback_image_gate \
  scripts.test_start_container
"${PLATFORM_PYTHON}" scripts/check_yaml.py
"${PLATFORM_PYTHON}" scripts/platform_eval.py
"${PLATFORM_PYTHON}" scripts/repository_integrity.py
if [[ "${PLATFORM_SKIP_EVAL_RESULTS:-0}" == "1" ]]; then
  "${PLATFORM_PYTHON}" -m scripts.governance_eval --skip-eval-results
else
  "${PLATFORM_PYTHON}" -m scripts.governance_eval
  "${PLATFORM_PYTHON}" scripts/eval_harness.py --check-results agent/eval-results.json
fi

POSTGRES_PASSWORD=compose-validation-only docker compose config --quiet

git diff --check -- \
  .dockerignore \
  .github \
  .gitignore \
  Dockerfile \
  docker-compose.yml \
  infra \
  scripts

if [[ "${PLATFORM_BUILD_IMAGE:-0}" == "1" ]]; then
  docker build --target runtime --tag ai-native-content-agency:validation .
fi

printf 'platform_validation=PASS\n'
