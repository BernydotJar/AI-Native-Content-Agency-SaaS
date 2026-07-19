# Local Foundation Verification — 2026-07-18

Updated: 2026-07-19T19:08:21Z

## Verdict

The current working tree contains a production-oriented local foundation with repaired real-transport, PostgreSQL, rollback and cloud-drift gates. Local producer and focused critic validation are green, but release is not: the current executable eval result, exact-tree GitHub CI, a distinct eligible reviewer and a final evaluator remain incomplete. Main and phase-environment protections are live and fail closed. Current recommendation: `DENY_RELEASE`; cloud: `DENY_APPLY`.

## Current local producer evidence

| Gate | Result |
|---|---|
| Backend tests | PASS_LOCAL — 58 pytest cases plus seven legacy unittest cases; 24/24 repeated races and timeout critic pass |
| Ruff check / format; mypy; canonical OpenAPI | PASS |
| Alembic and PostgreSQL integration | PASS — fresh migrations 0001–0003, single same-key execution, cross-tenant denial and app recreation |
| Frontend tests | PASS — 47 |
| Frontend lint / typecheck / contract / build | PASS |
| Live Playwright | PASS — fresh approval, rejection and app-only restart 3/3 against SPA/FastAPI/PostgreSQL |
| Terraform/static platform | PASS_LOCAL — nine roots, 24 Terraform tests, 65 script tests and 63 controls; result remains `DENY_APPLY` |

These counts describe the uncommitted repair working tree. GitHub Actions run `29672994585` passed the prior committed HEAD `34c3489`; it is not current-tree CI evidence.

## Behavioral coverage added by the repair

- Approval and rejection originate in the browser, cross real HTTP, persist in PostgreSQL and restore on reload/explicit refresh.
- Versioned tenant/principal identity is directly queryable through the protected identity endpoint.
- Every approval directly records its idempotency key in the row, response and audit payload. Migration from revision 0002 backfills only a safe one-to-one durable command record and fails closed otherwise.
- Explicit tests cover wrong policy, nonexistent run, provider timeout rollback, duplicate run delivery/event replay and migration failure.
- PostgreSQL integration proves wrong-tenant read and approval denial.
- HTTP smoke asserts exactly eight artifacts/evidence after sandbox approval.

## Reproducibility and delivery

- Frozen backend development dependencies include PyYAML, closing the prior clean-environment failure in `scripts/validate_platform.sh`.
- CI includes `ruff format --check` and installs locked Chromium before live E2E.
- The combined image/Compose design remains non-root with PostgreSQL health, one-shot Alembic ordering and same-origin SPA/API serving.
- A separate non-deployed image stage supplies locked integration dependencies; both stages use UID 10001 and `httpx2` is absent from runtime.
- Manual visual/accessibility inspection remains unproven because the required in-app browser returned zero instances. Playwright is transport/behavior evidence only.

## Static cloud repairs

- WIF binds immutable numeric GitHub owner/repository IDs.
- Existing projects require explicit evidence-backed Terraform import; no data-only implicit adoption remains.
- Bootstrap/dev project IDs differ and required labels are protected.
- Region, repository identity and project/channel provenance are bound from foundation into runtime; the three foundation phase accounts must come from the exact bootstrap project.
- Routine deploy IAM contains 16 permissions and excludes service/job deletion and service IAM mutation; foundation grants service-only `roles/run.servicesInvoker` and runtime owns no service IAM member.
- A separate two-permission role can create/update—but not upload/delete—the immediate-predecessor rollback tag only after attestation and preflight.
- State versioning and seven-day soft deletion preserve recovery without a retention policy that traps `.tflock`.
- Registry cleanup covers tagged and untagged versions older than seven days after keeping the 20 most recent plus `rollback-current`; runtime and rollback deploy only by immutable foundation-repository digest.
- Post-apply now verifies exact runtime roles, named application/migration/proxy images, WIF/impersonation, state boundaries, complete repository IAM and both custom roles.
- Terraform creates or imports Monitoring channels, protects them from destruction and blocks alert, budget and costly/runtime resources until verification plus evidence pass.

No static result proves a real GCP plan, permissions, policies, quotas, regional availability, cost, runtime health or drift.

## Pending local gates

- Root-owned final-tree eval result generation and exact traceability execution.
- Commit/push and exact-tree GitHub Actions.
- Exact-tree validation under the now-required main checks plus a distinct eligible reviewer for the protected `dev` environment.
- New independent readiness evaluation.

See [`readiness-audit-2026-07-19.md`](readiness-audit-2026-07-19.md) for the authoritative hard blockers.
