# INC-037 — GCP staging bootstrap

Updated: 2026-07-28

## Objective

Replace the ephemeral Cloudflare Quick Tunnel path with a production-oriented, stable
Google Cloud foundation while preserving a strict no-cost/no-apply boundary during
bootstrap development.

## Authenticated project inspection

The persistent Cloud Sandbox workstation now contains:

```text
Google Cloud CLI 578.0.0
Terraform 1.15.8
Google provider 7.41.0 (locked)
```

Interactive user authentication and Application Default Credentials succeeded. The
selected project is `ai-native-content-agency-saas` in `us-central1`.

Read-only inspection confirmed:

- project lifecycle: active;
- billing: disabled;
- relevant enabled APIs before this increment: only Service Usage;
- Cloud Run services: none;
- Artifact Registry repositories in `us-central1`: none;
- Cloud SQL instances: none;
- Secret Manager secrets: none.

No API, repository, secret, identity, deployment or paid resource was created.

## Implemented infrastructure contract

`infra/gcp` now provides a fail-closed Terraform module for:

- explicit Google API enablement;
- one empty Docker Artifact Registry repository;
- separate Cloud Run runtime and GitHub deployer service accounts;
- GitHub Workload Identity Federation without service-account keys;
- OIDC restriction to the exact repository and `refs/heads/main`;
- eight empty Secret Manager containers, with values managed out-of-band;
- per-secret runtime access instead of project-wide secret access;
- an optional Cloud Run service pinned to an immutable Artifact Registry digest;
- numeric, pinned Secret Manager versions rather than `latest`;
- scale-to-zero defaults and a maximum of two instances;
- all publication, political, paid-media and model-effect switches disabled.

Cloud Run remains impossible to plan unless bootstrap is enabled, an immutable image is
provided and all required database, identity, encryption and social-provider secret
references use numeric versions.

## Plan evidence

### Zero-resource plan

Against the authenticated project with both feature flags false:

```text
resource_changes=0
create=0
update=0
delete=0
resource_creation_enabled=false
cloud_run_enabled=false
```

### Bootstrap-only plan

With `enable_bootstrap=true` and `enable_cloud_run=false`:

```text
creates=33
project_services=7
artifact_repositories=1
service_accounts=2
workload_identity_pools=1
workload_identity_providers=1
project_iam_members=3
service_account_iam_members=2
secret_containers=8
per_secret_runtime_bindings=8
```

Explicitly absent:

```text
Cloud Run services
Cloud SQL instances
Compute instances
GKE clusters
secret versions or values
service-account keys
non-create actions
```

## Validation

- `terraform fmt -check`: pass;
- `terraform init -backend=false`: pass;
- `terraform validate`: pass;
- Terraform fail-closed tests: 3 pass, 0 fail;
- real authenticated zero-resource plan: pass;
- real authenticated bootstrap plan audit: pass;
- no project-wide Secret Manager accessor grant;
- OIDC repository and branch restrictions: pass.

## Remaining gate

The project has billing disabled. No Cloud Run deployment or persistent managed database
can be claimed. Applying the 33-resource bootstrap plan remains a separate operator gate,
even though it contains no compute or database resources. A later database decision must
be explicit because a managed PostgreSQL service is not assumed to be free.

Release recommendation: `DENY_RELEASE`

Cloud recommendation: `DENY_APPLY`
