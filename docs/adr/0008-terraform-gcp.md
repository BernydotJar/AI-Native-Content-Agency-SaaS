# ADR 0008 — Terraform-managed GCP foundation

- Decision: Use Terraform for an isolated bootstrap and split dev foundation/runtime states; define but never apply staging/prod in this iteration.
- Status: Accepted; apply externally blocked until open billing exists
- Context: Managed GCP services reduce initial operations, but manual resources would create drift.
- Alternatives: Manual console; Kubernetes; one broad Terraform root/identity; split Terraform foundation/runtime roots and phase identities.
- Evidence: Discovery found no related project, zero visible organizations, and six visible billing accounts all closed.
- Chosen option: Parameterized project IDs/parent/billing/region; a separately administered foundation for APIs, IAM, registry, SQL, alert delivery and budget; a narrow runtime root for private Cloud Run; three exact-workflow/environment WIF identities for build/resource-read-only plan/apply; condition-scoped versioned state; and exact-plan attestation, cost, evidence and rollback gates.
- Trade-offs: Two state roots, three identities, custom state roles and an exact custom runtime-deployer role add bootstrap and operator work. Plan still needs to create/delete Terraform's ephemeral runtime `.tflock`, but it cannot mutate `.tfstate`; apply can mutate only runtime state. The deployer gets only the required Cloud Run service/job operations, repository-scoped image read, reviewed viewer roles and `actAs` on one runtime service account—not `roles/run.admin`. These controls keep routine deployment from owning foundation resources/state. Managed services still incur ongoing cost.
- Consequences: No resource may target the unrelated configured project. Foundation changes require a separately authorized and reviewed plan. Routine apply accepts only the saved runtime plan whose hash, full tracked tree, commit, image, workflow, actor, independent reviewer and run URL match a fresh `ALLOW_DEV_APPLY` attestation verified before authentication. A real plan/apply still waits for billing and target authorization.
- Review trigger: Billing/parent selection, organization policy, measured workload, or a staging authorization.
- Date: 2026-07-18
- Owner: Orchestrator
