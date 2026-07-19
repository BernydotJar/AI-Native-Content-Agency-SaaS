#!/usr/bin/env bash
set -euo pipefail

PLATFORM_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PLATFORM_ROOT}"

export TF_IN_AUTOMATION=1
export TF_INPUT=0
export PYTHONPYCACHEPREFIX="${TMPDIR:-/tmp}/agency-platform-pycache"

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

python3 -m py_compile \
  scripts/check_yaml.py \
  scripts/dev_apply_gate.py \
  scripts/gcp_permission_preflight.py \
  scripts/generate_ts_contracts.py \
  scripts/http_smoke.py \
  scripts/platform_eval.py \
  scripts/post_apply_verify.py \
  scripts/repository_integrity.py \
  scripts/run_cloud_migrations.py \
  scripts/start_container.py \
  scripts/terraform_plan_gate.py
python3 -m unittest \
  scripts.test_dev_apply_gate \
  scripts.test_gcp_permission_preflight \
  scripts.test_http_smoke \
  scripts.test_post_apply_verify \
  scripts.test_repository_integrity \
  scripts.test_start_container
python3 scripts/check_yaml.py
python3 scripts/platform_eval.py
python3 scripts/repository_integrity.py

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
