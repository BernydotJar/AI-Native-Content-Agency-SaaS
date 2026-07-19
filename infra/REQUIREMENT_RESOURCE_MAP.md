# Requirement-to-resource and cost map

| Requirement | Implemented behavior | Terraform resource/module | Validation | Cost implication |
|---|---|---|---|---|
| DLV-005, GCP-000 | Explicit dev-only foundation/runtime states; staging/prod are non-executable definitions. | `bootstrap`, `environments/dev`, `environments/dev_runtime` | fmt, init/validate, mock tests, state-prefix and workflow scans | Terraform itself has no service charge; provisioned resources do. |
| GCP-004, DLV-008 | Versioned uniform-access remote state and three keyless GitHub OIDC phases restricted to exact owner/repository/main/direct workflow/environment. Plan state writes are lock-only; apply writes are runtime-prefix-only. | State bucket, custom/conditional state roles and `github_wif` | Exact WIF/state-condition tests, disposable lock probe, phase separation and no-key/basic-role scan | Low bucket storage/operation cost; WIF has no expected material direct cost. |
| DLV-003 | One non-root combined SPA/API image. | Docker multi-stage build; Artifact Registry | Docker build, UID assertion, immutable digest validation | Private image storage and egress; cleanup retains only recent images. |
| APP-002, DLV-001 | PostgreSQL runtime with checked migrations before cloud readiness and an idempotent evidence job. | `cloud_sql`, local PostgreSQL Compose, Cloud Run startup migration and migration job | Compose ordering; Alembic/advisory-lock/startup tests; connector/static checks | Cloud SQL is expected to dominate dev cost; price and tier availability require a target-region plan. |
| SEC-001, SEC-002 | Cloud Run is IAM-private; development headers remain behind Cloud IAM and production is not configured. | `cloud_run`, service IAM members | `invoker_iam_disabled=false`; rejection of public principals; backend security tests | Scale-to-zero compute plus request/egress charges. Proxy sidecar adds per-instance CPU/memory. |
| SEC-004, SEC-005 | Passwordless database access, no generated secrets, no authorized networks. | Cloud SQL IAM user, connector enforcement, Auth Proxy sidecar, Python Connector migration job | Static scan and mock plan assertions | No Secret Manager container is created because no application secret is consumed. |
| APP-014 | Structured runtime logs, stable step/run identities, 5xx alert and explicit notification recipients. | Cloud Run logging plus Monitoring alert policy and uniquely resolved enabled/verified email channels | Log tests, Terraform channel-type/status mock assertions and post-apply verifier | Logging/Monitoring charges depend on volume; no custom high-volume metric is created. |
| GCP-005, GCP-011 | Bounded dev spend visibility with explicit delivery targets. | Billing budget at 50%, 90%, and 100% thresholds plus required verified email channels | Budget/channel mock assertions; test-email receipt remains a billing-owner gate | Budgets alert but do not cap spend. Default is USD 50 and remains configurable only within a bounded range. |
| GCP-007, GCP-009 | Routine apply cannot substitute source, image, plan, workflow or reviewer evidence and cannot administer the foundation. | `environments/dev_runtime`, phase IAM, deploy workflow | Exact-attestation tests before authentication; plan gate; post-apply role/resource/log/smoke verification; second plan | No added service charge; evidence retention and verification incur small CI/API usage. |
| GCP-003 | Optional isolated bootstrap/dev project creation with no default network. | `google_project` roots | Parent/billing preconditions; no implicit provider project | Project creation is free; enabled services and resources are not. |

## Intentionally absent

Pub/Sub, Cloud Tasks, VPC connectors, NAT, load balancers, GKE, additional databases, artifact buckets, and Secret Manager containers are absent because no implemented behavior consumes them. Staging and production contain no resources. These omissions reduce attack surface, drift, and recurring cost.

## Cost confidence

No real target project, open billing account, allowed region, saved plan, or provider price estimate exists. Therefore no exact monthly cost is claimed. Before a real plan, verify shared-core tier availability, storage/backups, Cloud Run sidecar allocation, Artifact Registry retention, logging volume, and regional egress. Infrastructure cost incurred by this task: `0 observed external cloud spend`.
