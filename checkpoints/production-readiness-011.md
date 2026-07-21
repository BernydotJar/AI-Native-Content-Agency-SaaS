# Production readiness checkpoint 011

- **Date:** 2026-07-21
- **Branch:** `agent/production-readiness`
- **Increment:** shared PostgreSQL runtime state and offline SQLite migration
- **External deployment or publication:** none

## Acceptance decision

This increment is accepted for repository-level production readiness. PostgreSQL now provides one transactional state boundary for horizontally replicated application processes, while SQLite remains the default for local and explicitly single-replica operation.

The acceptance does not claim managed PostgreSQL availability, backup recovery, production load capacity or pod execution in the local agentless K3s control plane.

## Delivered controls

- Shared PostgreSQL storage for runs, audit events, browser sessions, authentication-rate-limit buckets and tenant memories.
- Cross-replica locking and conflict handling for Greenlight decisions and run updates.
- Bounded `pg8000` connection pool with health checks, timeout, rollback, broken-connection discard and deterministic shutdown.
- Schema version `1` initialized under an advisory transaction lock and rejected when an unknown version already exists.
- PostgreSQL URL validation with explicit TLS modes and rejection of unknown or duplicate options.
- Offline SQLite migration that is dry-run by default, applies in one transaction to an empty target and rejects replay.
- Helm backend selection, SQLite single-replica guard, PostgreSQL Secret reference, rolling update and PostgreSQL-only PodDisruptionBudget.
- Terraform inputs for backend topology and an existing Secret reference only; the database URL is not a Terraform value.
- Hash-locked permissively licensed PostgreSQL driver graph. The earlier LGPL driver candidate was rejected rather than weakening the license policy.
- Dedicated real-PostgreSQL local/CI gate.

## Evidence

### Runtime and migration

```text
postgres_version=PostgreSQL 15.18
backend_wheel=agency_runtime-0.7.0-py3-none-any.whl
postgres_driver=pg8000-1.31.5
backend_tests=49/49 pass
multi_replica_run_audit_greenlight=pass
shared_sessions_rate_limits=pass
cross_replica_credential_revocation=pass
shared_tenant_memory=pass
pool_timeout_and_url_guards=pass
schema_version_fail_closed=pass
migration_dry_run=pass
migration_apply=pass
migration_source_target_counts=pass
migration_auth_failure_totals=pass
migration_replay_guard=pass
pip_check=pass
cleanup=pass
```

The PostgreSQL gate built and installed the wheel using only dependencies from the hash-locked build and test graphs. PostgreSQL ran as an unprivileged local user and its databases, process, virtual environment and temporary files were removed on exit.

### Package, deployment and infrastructure

```text
frontend_tests=33/33 pass
frontend_lint=pass
frontend_build=pass
backend_sqlite_and_postgresql_suite=pass
production_image_uid_gid=10001:10001
full_stack_smoke=pass
helm_lint=pass
helm_sqlite_render=pass
helm_postgresql_render=pass
helm_negative_guards=pass
terraform_fmt_init_validate=pass
kubernetes_api=pass
helm_server_dry_run=pass
terraform_plan_apply_destroy=pass
terraform_secret_value_in_state=absent
workload_execution=not_validated_agentless_control_plane
cleanup=pass
```

The local Kubernetes result retains the previously documented boundary: K3s agentless provides a real Kubernetes API server but no kubelet/runtime/CNI, so workload execution is not claimed. The production image was executed independently through Buildah.

### Dependency and supply-chain policy

```text
python_locks_byte_identical=pass
python_required_hashes=pass
psycopg_dependency=absent
license_policy=pass
vulnerability_policy=pass
sbom_generation=pass
oci_export=pass
cosign_offline_verification=pass
workflow_action_pins=pass
actionlint=pass
```

The precommit image rebuild and SBOM scan accepted the `pg8000` graph without a license-policy exception. The complete supply-chain gate was then repeated with a clean worktree at implementation commit `27c4a3e`; OCI export, SBOM, vulnerability and license policies, in-toto provenance and both offline Cosign verifications passed, and the gate left the tracked tree clean.

```text
supply_chain_clean_head=pass
provenance_source_commit=27c4a3ef9e7741dae7df0c5ff965fab0ca5299bb
repository_clean_after_supply_chain=pass
```

### Cloud Sandbox MCP `git_push` correction

A disposable bare Git remote was created inside the persistent workspace. `Cloud_Sandbox_MCP.git_push` pushed the current `HEAD` to a temporary branch and the result was checked directly in the bare repository.

```text
git_push_local_bare_remote=pass
remote_ref_equals_head=pass
persistent_checkout_mount_unchanged=pass
checkout_and_git_ownership=node:node
ownership_preserved=pass
container_fingerprint_unchanged=pass
dockerd_started=false
docker_in_docker_used=false
temporary_remote_cleanup=pass
```

This test did not contact `origin`, GitHub or any external network remote.

## Architecture decisions

- [ADR 0007](../docs/adr/0007-postgresql-durable-state.md) records the shared-state backend, driver/license decision and migration boundary.
- [PostgreSQL durable runtime state](../docs/POSTGRESQL_PERSISTENCE.md) defines configuration, deployment, migration, rollback and operational requirements.

## Residual production requirements

- Provision PostgreSQL with approved high availability, TLS, least-privilege credentials, monitoring and tested point-in-time recovery.
- Execute load and soak tests using the intended replica count and database connection budget.
- Execute pods on a host or cluster with delegated writable cgroup v2 and a kubelet/runtime/CNI, or use an approved external cluster.
- Schedule the SQLite cutover as a maintenance operation with verified backup and rollback ownership.
- Define a migration framework before introducing schema version `2`.

## Git safety

No push to `origin`, production deployment, package publication, external infrastructure creation, paid action or protected-branch modification was performed.
