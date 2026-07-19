# GCP-0 Discovery Report — 2026-07-18

Updated: 2026-07-19T05:25:00Z

Status: `PARTIAL` / `DENY_APPLY` — read-only discovery identified an eligibility and authorization blocker; no mutation was performed.

## Identity and tooling

- One active CLI account is configured; its full address is intentionally omitted here.
- ADC refresh succeeds when token output is redirected to `/dev/null`; no access or refresh token was printed or recorded.
- Active `gcloud` project: `meridian-hr-crm`. It is unrelated and prohibited as a target.
- Configured compute/Run region and zone: unset.
- Visible organizations: zero. This may mean no organization or insufficient hierarchy visibility.
- Folders were not enumerated because no organization is visible.

## Billing and projects

- Visible billing accounts: six.
- Accounts reporting `open=True`: zero.
- Billing identifiers remain masked and are not copied into versioned evidence.
- Visible projects: 17.
- One exact product-name candidate now exists:

| Field | Read-only observation |
|---|---|
| Project ID | `ai-native-content-agency-saas` |
| Display name | `AI-Native-Content-Agency-SaaS` |
| Lifecycle state | `ACTIVE` |
| Creation time | `2026-07-19T04:27:27.280Z` |
| Billing | Disabled; no billing account attached |
| Parent | None visible |
| Required Terraform labels | Absent |
| Buckets | None observed |
| Service accounts | None observed |
| Workload identity pools | None observed |
| Artifact Registry / Cloud Run / Cloud SQL APIs | Disabled or unavailable in the current project state |

Default platform APIs are enabled, including service usage, storage, logging and monitoring plus several BigQuery/Dataplex defaults. API presence is not evidence that the project belongs to this iteration.

## Candidate disposition

The candidate's creator, authorization, intended lifecycle and bootstrap/dev role are unknown. Its matching name does not establish provenance. It is not in Terraform state, has no versioned adoption record and cannot silently satisfy both mandatory project-isolation roles.

Before it appears in a real plan, an explicit decision must either:

1. reject it as out of scope; or
2. assign it to exactly one of bootstrap/dev and use `ADOPT_EXISTING` with reviewed `gcp-project-adoption.v1` evidence plus the declarative import block.

A distinct second project remains required. Adoption must inspect parent, billing, labels, default resources/APIs and any plan drift; no manual console resource creation is allowed.

## Unavailable target evidence

Without an open billing account, explicit parent/no-organization choice, distinct project roles and region, the session cannot truthfully complete:

- granular project/billing/API/IAM/WIF/state/resource permission tests;
- effective organization policies and project quotas;
- Cloud SQL tier and resource availability in a selected region;
- a target-specific price envelope;
- a saved bootstrap/foundation/runtime plan and JSON;
- cloud critique/security/evaluator approval of an exact plan;
- apply, state migration, post-apply verification or second no-change plan.

The active identity currently has a direct Owner binding on the candidate, but a broad role name is not granular permission proof and does not grant adoption authority by itself.

## Exact resume condition

1. At least one intended visible billing account reports `open=True`.
2. If more than one is eligible, select the intended account explicitly.
3. Authorize the parent or documented no-organization placement, region and two distinct non-personal project IDs.
4. Decide the candidate's exact disposition and bind any adoption to reviewed evidence; never infer it from its name.
5. Run target-specific granular permissions, policy, quota, API, regional availability and price preflight.
6. Keep `meridian-hr-crm` excluded.
7. Only then produce saved plans and resume the independent critique/evaluator sequence.

## Mutation and cost statement

No GCP project, billing link, API, IAM policy, service account, WIF pool, bucket, registry, database, service, state or plan was created or changed by this work. Infrastructure cost observed from this task: `0 observed external cloud spend`.
