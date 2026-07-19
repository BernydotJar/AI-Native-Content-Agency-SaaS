# Local Foundation Verification — 2026-07-18

## Verdict

The repository now has a production-oriented local foundation and a parameterized, gated GCP dev path. Application release evidence is locally green; cloud apply is not authorized. Current recommendation: `DENY_APPLY`.

## Application evidence

| Gate | Result |
|---|---|
| Backend pytest | PASS — 40/40 on Python 3.13; independent 40/40 on Python 3.9 |
| Legacy unittest | PASS — 16/16 |
| Ruff / mypy / OpenAPI | PASS |
| Frontend tests | PASS — 45/45 |
| Frontend lint / typecheck / contract / build | PASS |
| npm audit | PASS — zero vulnerabilities |
| Python runtime lock audit | PASS — no known vulnerabilities |

Independent adversarial work verified tenant isolation, request byte limits without trusting Content-Length, manifest TOCTOU rollback, structured safe 500/503 errors, identity bootstrap concurrency, stable idempotent retries and stale-response protection.

## Container and persistence evidence

- The combined image is pinned at its bases, installs hash-locked dependencies and runs as UID/GID `10001:10001`.
- Compose starts PostgreSQL 15, runs Alembic to completion, then exposes the app only on `127.0.0.1:8080` through a separated edge network.
- `scripts/http_smoke.py` created a mission, completed the eight-step run and exact approval, and asserted `external_side_effects=false` plus a single `publication_performed=false` package.
- Run `run-df042624cbf74e5bb4d2e89fa055fe10` remained readable and complete after the rebuilt app and PostgreSQL containers were recreated while preserving the named volume.
- The CI platform job now repeats the live Compose migration and HTTP flow.

## Terraform evidence

- All eight roots have identical Google provider 7.40.0 locks with signed hashes for Linux AMD64 and macOS ARM64.
- `terraform fmt`, readonly backend-free init, validate and two mock-provider tests pass.
- Thirty static controls pass for public IAM, basic roles, service-account keys, WIF scope, Cloud SQL connector/IAM auth, Cloud Run invocation, local Compose boundaries, pinned delivery and state/plan hygiene.
- Static success explicitly returns `DENY_APPLY`; it is not evidence of permissions, policies, quotas, price, connectivity, drift or a safe real plan.

## Unproven / blocked

- Interactive visual QA: the required in-app browser runtime returned an empty browser list.
- Real GCP plan/apply: all visible billing accounts are closed; target hierarchy/project/region are absent.
- Post-apply authenticated/unauthenticated probes and second no-change plan cannot exist before an authorized exact apply.
